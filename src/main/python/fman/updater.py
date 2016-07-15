from os.path import join, pardir, dirname
from threading import Thread

import sys

class EskyUpdater(Thread):
	def __init__(self, executable, update_url):
		super().__init__()
		from esky import Esky
		self.esky = Esky(executable, update_url)
	def run(self):
		self.esky.auto_update()

class OSXUpdater:
	def __init__(self, app, appcast_url):
		self.app = app
		self.appcast_url = appcast_url
		self._objc_namespace = dict()
		self._sparkle = None
	def start(self):
		from objc import pathForFramework, loadBundle, selector
		frameworks_dir = join(dirname(sys.executable), pardir, 'Frameworks')
		fmwk_path = pathForFramework(join(frameworks_dir, 'Sparkle.framework'))
		loadBundle('Sparkle', self._objc_namespace, bundle_path=fmwk_path)
		self.app.aboutToQuit.connect(self._about_to_quit)
		SUUpdater = self._objc_namespace['SUUpdater']
		self._sparkle = SUUpdater.sharedUpdater()
		self._sparkle.setAutomaticallyChecksForUpdates_(True)
		self._sparkle.setAutomaticallyDownloadsUpdates_(True)
		NSURL = self._objc_namespace['NSURL']
		self._sparkle.setFeedURL_(NSURL.URLWithString_(self.appcast_url))
		self._sparkle.checkForUpdatesInBackground()
	def _about_to_quit(self):
		if self._sparkle.updateInProgress():
			# Installing the update takes quite some time. Hide the dock icon so
			# the user doesn't think fman froze:
			self._hide_dock_window()
		self._notify_sparkle_of_app_shutdown()
	def _hide_dock_window(self):
		NSApplication = self._objc_namespace['NSApplication']
		app = NSApplication.sharedApplication()
		app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
	def _notify_sparkle_of_app_shutdown(self):
		# Qt apps don't receive the NSApplicationWillTerminateNotification
		# event, which Sparkle relies on. Broadcast it manually:
		NSNotificationCenter = self._objc_namespace['NSNotificationCenter']
		NSNotificationCenter.defaultCenter().postNotificationName_object_(
			"NSApplicationWillTerminateNotification", None
		)

NSApplicationActivationPolicyProhibited = 2
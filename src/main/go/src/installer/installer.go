package main

import (
	"bufio"
	"errors"
	"golang.org/x/sys/windows/registry"
	"os"
	"os/user"
	"strings"
	"installer/data"
	"path/filepath"
	"winutil"
	"text/template"
	"io/ioutil"
	"os/exec"
	"syscall"
	"flag"
)

const Version = "${version}"
const ProductId = `{91F6D922-553C-4E18-8991-53B3A925ACDA}`

func main() {
	doInstallPtr := flag.Bool("install", false, "Install fman")
	doUpdatePtr := flag.Bool("update", false, "Update fman")
	flag.Parse()

	var installDir string
	if *doInstallPtr {
		installDir = getInstallDirWhenManagedByOmaha()
		extractAssets(installDir)
		createRegistryKeysForUninstaller(installDir)
		addContextMenuEntriesToExplorer(installDir)
		updateVersionInRegistry()
		createStartMenuShortcut(installDir)
		launchFman(installDir)
	} else if *doUpdatePtr {
		installDir = getInstallDirWhenManagedByOmaha()
		extractAssets(installDir)
		// TODO: Remove this line after October 2017. It only serves to
		// migrate versions < 0.6.2, for which addContextMenuEntriesToExplorer
		// wasn't called during install:
		addContextMenuEntriesToExplorer(installDir)
		updateVersionInRegistry()
		removeOldVersions(installDir)
	} else {
		installDir = getDefaultInstallDir()
		extractAssets(installDir)
		createRegistryKeysForUninstaller(installDir)
		createStartMenuShortcut(installDir)
		launchFman(installDir)
	}
}

func getInstallDirWhenManagedByOmaha() string {
	executablePath, err := winutil.GetExecutablePath()
	check(err)
	result := executablePath
	prevResult := ""
	for filepath.Base(result) != "fman" {
		prevResult = result
		result = filepath.Dir(result)
		if result == prevResult {
			break
		}
	}
	if result == prevResult {
		msg := "Could not find parent directory 'fman' above " + executablePath
		check(errors.New(msg))
	}
	return result
}

func getDefaultInstallDir() string {
	localAppData := os.Getenv("LOCALAPPDATA")
	if localAppData == "" {
		panic("Environment variable LOCALAPPDATA is not set.")
	}
	return filepath.Join(localAppData, "fman")
}

func extractAssets(installDir string) {
	for _, relPath := range data.AssetNames() {
		bytes, err := data.Asset(relPath)
		check(err)
		absPath := filepath.Join(installDir, relPath)
		check(os.MkdirAll(filepath.Dir(absPath), 0755))
		f, err := os.OpenFile(absPath, os.O_CREATE, 0755)
		check(err)
		defer f.Close()
		w := bufio.NewWriter(f)
		_, err = w.Write(bytes)
		check(err)
		w.Flush()
	}
}

func isUserInstall() bool {
	return strings.HasPrefix(os.Args[0], os.Getenv("LOCALAPPDATA"))
}

func createRegistryKeysForUninstaller(installDir string) {
	regRoot := getRegistryRoot()
	uninstKey := `Software\Microsoft\Windows\CurrentVersion\Uninstall\fman`
	writeRegStr(regRoot, uninstKey, "", installDir)
	writeRegStr(regRoot, uninstKey, "DisplayName", "fman")
	writeRegStr(regRoot, uninstKey, "Publisher", "Michael Herrmann")
	uninstaller := filepath.Join(installDir, "uninstall.exe")
	uninstString := `"` + uninstaller + `"`
	if isUserInstall() {
		uninstString += " /CurrentUser"
	} else {
		uninstString += " /AllUsers"
	}
	writeRegStr(regRoot, uninstKey, "UninstallString", uninstString)
}

func addContextMenuEntriesToExplorer(installDir string) {
	fmanExe := getFmanExePath(installDir)
	addExplorerContextMenuEntryForFolders("Open in fman", fmanExe)
	addExplorerContextMenuEntryInFolders("Open fman here", fmanExe)
	addExplorerContextMenuEntryForFiles("Highlight in fman", fmanExe)
}

func addExplorerContextMenuEntryForFolders(title string, executable string) {
	addExplorerContextMenuEntry(`directory\shell\` + title, executable)
}

func addExplorerContextMenuEntryInFolders(title string, executable string) {
	addExplorerContextMenuEntry(`directory\Background\shell\` + title, executable)
}

func addExplorerContextMenuEntryForFiles(title string, executable string) {
	addExplorerContextMenuEntry(`*\shell\` + title, executable)
}

func addExplorerContextMenuEntry(regKey string, executable string) {
	var regRoot registry.Key
	var parentRegKey string
	if isUserInstall() {
		regRoot = registry.CURRENT_USER
		parentRegKey = `Software\Classes\`
	} else {
		regRoot = registry.CLASSES_ROOT
		parentRegKey = ""
	}
	writeRegStr(regRoot, parentRegKey + regKey + `\command`, "", executable + ` "%V"`)
	writeRegStr(regRoot, parentRegKey + regKey, "icon", executable)
}

func updateVersionInRegistry() {
	regRoot := getRegistryRoot()
	updateKey := `Software\fman\Update\Clients\` + ProductId
	writeRegStr(regRoot, updateKey, "pv", Version + ".0")
	writeRegStr(regRoot, updateKey, "name", "fman")
}

func getRegistryRoot() registry.Key {
	if isUserInstall() {
		return registry.CURRENT_USER
	}
	return registry.LOCAL_MACHINE
}

func writeRegStr(regRoot registry.Key, keyPath string, valueName string, value string) {
	const mode = registry.WRITE|registry.WOW64_32KEY
	key, _, err := registry.CreateKey(regRoot, keyPath, mode)
	check(err)
	defer key.Close()
	check(key.SetStringValue(valueName, value))
}

func createStartMenuShortcut(installDir string) {
	startMenuDir := getStartMenuDir()
	linkPath := filepath.Join(startMenuDir, "Programs", "fman.lnk")
	targetPath := filepath.Join(installDir, "fman.exe")
	createShortcut(linkPath, targetPath)
}

func getStartMenuDir() string {
	if isUserInstall() {
		usr, err := user.Current()
		check(err)
		return usr.HomeDir + `\AppData\Roaming\Microsoft\Windows\Start Menu`
	} else {
		return os.Getenv("ProgramData") + `\Microsoft\Windows\Start Menu`
	}
}

func createShortcut(linkPath, targetPath string) {
	type Shortcut struct {
		LinkPath string
		TargetPath string
	}
	tmpl := template.New("createLnk.vbs")
	tmpl, err := tmpl.Parse(`Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{{.LinkPath}}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{{.TargetPath}}"
oLink.Save
WScript.Quit 0`)
	check(err)
	tmpDir, err := ioutil.TempDir("", "fman")
	check(err)
	createLnk := filepath.Join(tmpDir, "createLnk.vbs")
	defer os.RemoveAll(tmpDir)
	f, err := os.Create(createLnk)
	check(err)
	defer f.Close()
	w := bufio.NewWriter(f)
	shortcut := Shortcut{linkPath, targetPath}
	check(tmpl.Execute(w, shortcut))
	w.Flush()
	f.Close()
	cmd := exec.Command("cscript", f.Name())
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	check(cmd.Run())
}

func launchFman(installDir string) {
	cmd := exec.Command(getFmanExePath(installDir))
	check(cmd.Start())
}

func getFmanExePath(installDir string) string {
	return filepath.Join(installDir, "fman.exe")
}

func removeOldVersions(installDir string) {
	versionsDir := filepath.Join(installDir, "Versions")
	versions, err := ioutil.ReadDir(versionsDir)
	check(err)
	for _, version := range versions {
		if version.Name() == Version {
			continue
		}
		versionPath := filepath.Join(versionsDir, version.Name())
		// Try deleting the main executable first. We do this to prevent a
		// version that is still running from being deleted.
		mainExecutable := filepath.Join(versionPath, "fman.exe")
		err = os.Remove(mainExecutable)
		if err == nil {
			// Remove the rest:
			check(os.RemoveAll(versionPath))
		}
	}
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}
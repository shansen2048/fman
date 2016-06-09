from PyQt5.QtWidgets import QMessageBox

def show_message_box(text, standard_buttons, default_button):
	msgbox = QMessageBox()
	msgbox.setText(text)
	msgbox.setStandardButtons(standard_buttons)
	msgbox.setDefaultButton(default_button)
	return msgbox.exec()
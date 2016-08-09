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

	if *doInstallPtr {
		extractAssets()
		createRegistryKeysForUninstaller()
		updateVersionInRegistry()
		createStartMenuShortcut()
		launchFman()
	} else if *doUpdatePtr {
		extractAssets()
		updateVersionInRegistry()
	}
}

func getInstallDir() string {
	executablePath, err := winutil.GetExecutablePath()
	check(err)
	result := executablePath
	for filepath.Base(result) != "fman" && result != "." {
		result = filepath.Dir(result)
	}
	if result == "." {
		msg := "Could not find parent directory 'fman' above " + executablePath
		check(errors.New(msg))
	}
	return result
}

func extractAssets() {
	for _, relPath := range data.AssetNames() {
		bytes, err := data.Asset(relPath)
		check(err)
		absPath := filepath.Join(getInstallDir(), relPath)
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

func createRegistryKeysForUninstaller() {
	regRoot := getRegistryRoot()
	uninstKey := `Software\Microsoft\Windows\CurrentVersion\Uninstall\fman`
	installDir := getInstallDir()
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

func createStartMenuShortcut() {
	startMenuDir := getStartMenuDir()
	linkPath := filepath.Join(startMenuDir, "Programs", "fman.lnk")
	targetPath := filepath.Join(getInstallDir(), "fman.exe")
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

func launchFman() {
	cmd := exec.Command(filepath.Join(getInstallDir(), "fman.exe"))
	check(cmd.Start())
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}
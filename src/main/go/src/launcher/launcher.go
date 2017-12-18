//go:generate goversioninfo -icon=Icon.ico

/*
Looks at directory "Versions" next to this executable. Finds the latest version
and runs the executable with the same name as this executable in that directory.
Eg.:
  fman.exe (=launcher.exe)
  Versions/
    1.0.0.0/
      fman.exe
    1.0.1.0
      fman.exe
-> Launches Versions/1.0.1.0/fman.exe.
*/

package main

import (
	"errors"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"winutil"
)

type Version [3]int
type Versions []Version

func main() {
	executable, err := winutil.GetExecutablePath()
	check(err)
	executableDir, executableName := filepath.Split(executable)
	versionsDir := filepath.Join(executableDir, "Versions")
	latestVersion, err := getLatestVersion(versionsDir)
	check(err)
	target := filepath.Join(versionsDir, latestVersion, executableName)
	cmd := exec.Command(target, os.Args[1:]...)
	check(cmd.Start())
}

func getLatestVersion(versionsDir string) (string, error) {
	potentialVersions, err := ioutil.ReadDir(versionsDir)
	if err != nil {
		return "", err
	}
	var versions Versions
	for _, file := range potentialVersions {
		if !file.IsDir() {
			continue
		}
		version, err := parseVersionString(file.Name())
		if err != nil {
			continue
		}
		versions = append(versions, version)
	}
	if len(versions) == 0 {
		errMsg := fmt.Sprintf("No valid version in %s.", versionsDir)
		return "", errors.New(errMsg)
	}
	sort.Sort(versions)
	return versions[len(versions)-1].String(), nil
}

func parseVersionString(version string) (Version, error) {
	var result Version
	err := error(nil)
	parts := strings.Split(version, ".")
	if len(parts) != len(result) {
		err = errors.New("Wrong number of parts.")
	} else {
		for i, partStr := range parts {
			result[i], err = strconv.Atoi(partStr)
			if err != nil {
				break
			}
		}
	}
	return result, err
}

func (arr Versions) Len() int {
	return len(arr)
}

func (arr Versions) Less(i, j int) bool {
	for k, left := range arr[i] {
		right := arr[j][k]
		if left > right {
			return false
		} else if left < right {
			return true
		}
	}
	fmt.Printf("%s < %s\n", arr[i], arr[j])
	return true
}

func (arr Versions) Swap(i, j int) {
	tmp := arr[j]
	arr[j] = arr[i]
	arr[i] = tmp
}

func (version Version) String() string {
	parts := make([]string, len(version))
	for i, part := range version {
		parts[i] = strconv.Itoa(part)
	}
	return strings.Join(parts, ".")
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}
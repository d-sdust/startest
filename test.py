#!/bin/python3

# Public domain.

import os
import subprocess
import textwrap
import argparse
import tomllib
from pathlib import Path

printfilter_str = {
        "ok":       0b01,
        "fail":     0b10,
        "both":     0b11,
        "never":    0b00,
};

class PrintFilter:
    # [0] Stdout OK
    # [1] Stdout Fail
    # [2] Stderr OK
    # [3] Stderr Fail
    state: int = 0b1010;

    def __init__(self, filter: str="") -> None:
        if filter == "":
            return;

        filters = filter.split("/");
        if len(filters) != 2:
            raise Exception(f"Invalid filter string: {filter}");

        self.state = printfilter_str[filters[0]];
        self.state |= (printfilter_str[filters[1]] << 2);

    def __str__(self) -> str:
        out = list(printfilter_str.keys())[list(printfilter_str.values()).index(self.state & 0b11)];
        inp = list(printfilter_str.keys())[list(printfilter_str.values()).index(self.state >> 2)];
        return f"{out}/{inp}";

class Test:
    fullpath: str;
    runner: str;
    ok: int = 0;
    extraflags: list[str] = [];
    printfilter: PrintFilter = PrintFilter();
    external: bool = False;

    def __init__(self,
                 fullpath: str,
                 runner: str,
                 ok: int,
                 external: bool,
                 extraflags: list[str],
                 printfilter: PrintFilter) -> None:
        self.fullpath = fullpath;
        self.runner = runner;
        self.ok = ok;
        self.external = external;
        self.extraflags = extraflags;
        self.printfilter = printfilter;

    def __str__(self) -> str:
        return f"""[[test]]
path = '{self.fullpath}'
ok = {self.ok}
runner = '{self.runner}'
flags = {self.extraflags}
print = '{self.printfilter}'
"""

    def run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run([self.runner, self.fullpath] + self.extraflags,
                       capture_output=True,
                       text=True);

class NoTestsException(Exception):
    def __init__(self, path: str) -> None:
        super().__init__(f"No tests found in {path}. Exiting.");

class Config:
    __dir: str = "./tests";
    __runner: str = "";
    tests: list[Test] = [];

    def __init__(self,
                 path: str = "./tests.toml") -> None:
        with open(path, "rb") as file:
            data = tomllib.load(file);

            try:
                head = data["startest"];
            except KeyError:
                raise Exception(f"""Could not parse the `[startest]` config header from {path},
so this file does not look like a right Startest config.""");

            # Parse the head.

            if "dir" in head:
                self.__dir = head["dir"];
            if "runner" in head:
                self.__runner = head["runner"];

            if not "test" in data:
                raise NoTestsException(path);

            for test in data["test"]:
                fullpath = None;
                runner = self.__runner;
                flags = [];
                printfilter = PrintFilter();
                external = False;
                ok = 0;

                if "file" in test:
                    fullpath = os.path.join(self.__dir, test["file"]);
                elif "path" in test:
                    external = True;
                    fullpath = test["path"];
                else:
                    raise Exception("`[[test]]` with neither `file` nor `path`.");

                if "flags" in test:
                    flags = test["flags"];

                if "runner" in test:
                    runner = test["runner"];

                if "ok" in test:
                    ok = test["ok"];

                if "print" in test:
                    printfilter = PrintFilter(test["print"]);

                self.tests.append(Test(
                    fullpath=fullpath,
                    runner=runner,
                    ok=ok,
                    external=external,
                    extraflags=flags,
                    printfilter=printfilter
                    ));

class Runner:
    __config: Config;
    __current: int = 1;
    __passed: int = 0;
    __failed: int = 0;

    def __init__(self, config: Config) -> None:
        self.__config = config;

    def run(self):
        print(f"\033[1;33m---[TEST {len(self.__config.tests)} total]---\033[0m");

        for test in self.__config.tests:
            test_name = "<NULL>";
            if test.external:
                test_name = test.fullpath;
            else:
                test_name = Path(test.fullpath).stem;

            print(f"\033[1;33m({self.__current}/{len(self.__config.tests)}) {test_name} ... \033[0m", end='');

            res = test.run();
            self.__current += 1;

            match res.returncode:
                case test.ok:
                    print("\033[0;32mOK\033[0m");
                    self.__passed += 1;

                    if (test.printfilter.state & 0b1) != 0:
                        print("      \033[1;34mstdout:\033[0m\n",
                            textwrap.indent(res.stdout, "      >>")
                            );
                    if (test.printfilter.state & 0b100) != 0:
                        print("      \033[1;34mstderr:\033[0m\n",
                            textwrap.indent(res.stderr, "      >>")
                            );
                case _:
                    print("\033[0;31mFAIL\033[0m");
                    self.__failed += 1;
                    if (test.printfilter.state & 0b10) != 0:
                        print("      \033[1;34mstdout:\033[0m\n",
                            textwrap.indent(res.stdout, "      >>")
                            );
                    if (test.printfilter.state & 0b1000) != 0:
                        print("      \033[1;34mstderr:\033[0m\n",
                            textwrap.indent(res.stderr, "      >>")
                            );

    def finish(self) -> int:
        print("\n\033[1;33m---[TEST SUMMARY]---\033[0m");
        if self.__failed == 0:
            print("\033[0;32mAll tests passed\033[0m")
        elif self.__passed == 0:
            print("\033[0;31mAll tests failed\033[0m")
        else:
            print(f"\033[0;32mPassed: {self.__passed}\033[0m")
            print(f"\033[0;31mFailed: {self.__failed}\033[0m")
        return self.__failed;


# Parse args.
ap = argparse.ArgumentParser(
        prog="Startest", description="Startest - A tiny yet flexible test runner by Stardust.")
ap.add_argument("-c", "--config",
                type=str,
                default="./tests.toml",
                help="Override config path.");
args = ap.parse_args();

try:
    config = Config(args.config);
except NoTestsException as e:
    print("\n\033[1;33m---[NO TESTS]---\033[0m")
    exit(0);

runner = Runner(config);

runner.run();
runner.finish();

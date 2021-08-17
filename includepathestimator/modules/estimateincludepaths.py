# Copyright 2021 NXP
# All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0

""" Include paths estimator
This script estimates include paths from raw C source code.
"""

import argparse
import glob
import re
import os
import mmap
from pathlib import Path, PurePath
import datetime
import time
from collections import OrderedDict, defaultdict, Counter
import yaml
import yamlordereddictloader

source_types = [".cpp", ".c", ".h", ".asm", ".s", ".S"]
known_system_includes = ['_ansi.h',
                         '_fake_defines.h',
                         '_fake_typedefs.h',
                         '_syslist.h',
                         'aio.h',
                         'alloca.h',
                         'ar.h',
                         'argz.h',
                         'assert.h',
                         'c_types.h',
                         'cerrno',
                         'cmath',
                         'complex.h',
                         'cpio.h',
                         'cstddef',
                         'cstdint',
                         'cstdio',
                         'cstdlib',
                         'cstring',
                         'ctype.h',
                         'dirent.h',
                         'dlfcn.h',
                         'emmintrin.h',
                         'endian.h',
                         'envz.h',
                         'errno.h',
                         'evntprov.h',
                         'evntrace.h',
                         'fastmath.h',
                         'fcntl.h',
                         'features.h',
                         'fenv.h',
                         'float.h',
                         'fmtmsg.h',
                         'fnmatch.h',
                         'ftw.h',
                         'getopt.h',
                         'glob.h',
                         'grp.h',
                         'iconv.h',
                         'ieeefp.h',
                         'immintrin.h',
                         'intrinsics.h',
                         'inttypes.h',
                         'iso646.h',
                         'langinfo.h',
                         'libgen.h',
                         'libintl.h',
                         'limits.h',
                         'locale.h',
                         'malloc.h',
                         'math.h',
                         'monetary.h',
                         'mqueue.h',
                         'ndbm.h',
                         'netdb.h',
                         'newlib.h',
                         'nl_types.h',
                         'paths.h',
                         'poll.h',
                         'process.h',
                         'pthread.h',
                         'pwd.h',
                         'reent.h',
                         'regdef.h',
                         'regex.h',
                         'sched.h',
                         'search.h',
                         'semaphore.h',
                         'setjmp.h',
                         'signal.h',
                         'smmintrin.h',
                         'spawn.h',
                         'stdarg.h',
                         'stdbool.h',
                         'stddef.h',
                         'stdint.h',
                         'stdio.h',
                         'stdlib.h',
                         'string.h',
                         'strings.h',
                         'stropts.h',
                         'sys/mkdev.h',
                         'sys/param.h',
                         'sys/reboot.h',
                         'sys/resource.h',
                         'sys/signal.h',
                         'sys/socket.h',
                         'sys/stat.h',
                         'sys/syscall.h',
                         'sys/time.h',
                         'sys/times.h',
                         'sys/types.h',
                         'sys/uio.h',
                         'sys/un.h',
                         'sys/wait.h',
                         'syslog.h',
                         'tar.h',
                         'termios.h',
                         'tgmath.h',
                         'time.h',
                         'trace.h',
                         'ulimit.h',
                         'unctrl.h',
                         'unistd.h',
                         'utime.h',
                         'utmp.h',
                         'utmpx.h',
                         'wchar.h',
                         'wctype.h',
                         'windows.h',
                         'winsock2.h',
                         'wmistr.h',
                         'wordexp.h',
                         'zlib.h']


def args():
    """Load arguments from command line."""
    parser = argparse.ArgumentParser(
        description="Include path estimator.",
        epilog=r"Example: python estimateincludepaths.py -r c:\GIT\mcu-sdk-2.0\middleware\lwip",
    )
    parser.add_argument(
        "-r",
        "--root",
        action="store",
        help=" Absolute path to source code root folder.",
    )
    return parser.parse_args()


def separator():
    """Return standard POSIX path separator."""
    return str(PurePath(os.sep).as_posix())


def source_files(source_folder):
    """Get list of source files from source folder."""
    sources = list()
    for source_type in source_types:
        sources.extend(
            glob.glob(
                source_folder +
                "/**/*" +
                source_type,
                recursive=True))
    sources = sorted(map(lambda path: PurePath(path).as_posix(), sources))
    return sources


def header_files(file_list):
    """Filter header files only from source files list."""
    return sorted({file for file in file_list if file.endswith(".h")})


def c_source_files(file_list):
    """Filter c source files only from source files list."""
    return sorted({file for file in file_list if file.endswith(".c")})


def header_folders(file_list):
    """List folders containing header files"""
    return sorted(set(map(lambda file: PurePath(
        file).parent.as_posix(), header_files(file_list))))


def c_source_folders(file_list):
    """List folders containing c source files"""
    return sorted(set(map(lambda file: PurePath(
        file).parent.as_posix(), c_source_files(file_list))))


def includes(file_list):
    """Extract list of includes used in each source file and attach it in data structure."""
    return sorted(
        {include for file in file_list for include in includes_from_file(file)}
    )


def includes_with_count(file_list):
    """Count includes used in source files."""
    counted_includes = Counter(
        [include for file in file_list for include in includes_from_file(file)]
    )
    return OrderedDict(counted_includes.most_common())


def internal_includes(include_list, file_list):
    """Return includes which could be mapped to internal source files
    (files in root folder and its sub folders). """
    internal_include_list = list()
    for include in include_list:
        include_tokens = include.split(separator())
        up_reference_count = include_tokens.count("..")
        for file in file_list:
            file_tokens = file.split(separator())
            if file_tokens[-len(include_tokens) +
                           up_reference_count:] == include_tokens[up_reference_count:]:
                internal_include_list.append(include)
    return sorted(set(internal_include_list))


def external_includes(include_list, internal_include_list):
    """Return external includes used in examined source files."""
    external_include_list = list(
        set(include_list) -
        set(internal_include_list))
    external_include_list = sorted(set(external_include_list))
    return external_include_list


def system_includes(include_list):
    """Return system includes used in examined source files."""
    return sorted(
        {include for include in include_list if include in known_system_includes})


def up_level_references_folders(
    include_path_candidate, up_reference_count, header_tokens
):
    """Get folders in scope of upper level references."""
    ambiguous_paths = list()
    subfolders = [path for path in os.scandir(
        include_path_candidate) if path.is_dir()]
    for path in subfolders:
        path = PurePath(path).as_posix()
        path_tokens = path.split(separator())
        origin_path_length = len(header_tokens) - 1
        if (len(path_tokens) > origin_path_length) and (
            len(path_tokens) <= origin_path_length + up_reference_count
        ):
            if path not in ambiguous_paths:
                ambiguous_paths.append(path)
    return ambiguous_paths


def record_header(database, header):
    """ambiguous_pathAdd header file into include path candidates database."""
    if header not in database.keys():
        database[header] = {"include_paths": []}
    if "path_notes" not in database[header].keys():
        database[header]["path_types"] = []
    return database


def record_ambiguous_paths(database, ambiguous_paths, header):
    """Add ambiguous path set into include path candidates database.
    Determine all possible include path variants in case of upper references '..'"""
    if not ambiguous_paths:
        database[header]["include_paths"].append(None)
        if "non_existing" not in database[header]["path_types"]:
            database[header]["path_types"].append("non_existing")
    else:
        if ambiguous_paths not in database[header]["include_paths"]:
            database[header]["include_paths"] = ambiguous_paths
            if "ambiguous" not in database[header]["path_types"]:
                database[header]["path_types"].append("ambiguous")
    return database


def record_optional_paths(database, include_path_candidate, header):
    """Add optional path set into include path candidates database.
    Optional include path if the source file location is
    identical location of included header file location"""
    if include_path_candidate not in database[header]["include_paths"]:
        database[header]["include_paths"].append(include_path_candidate)
        if "optional" not in database[header]["path_types"]:
            database[header]["path_types"].append("optional")
    return database


def record_mandatory_paths(database, include_path_candidate, header):
    """Add mandatory path set into include path candidates database.
    Mandatory include path is detected if the source file location is
    different than location of included header file location"""
    if include_path_candidate not in database[header]["include_paths"]:
        database[header]["include_paths"].append(include_path_candidate)
        if "mandatory" not in database[header]["path_types"]:
            database[header]["path_types"].append("mandatory")
    return database


def include_paths_for_include(source, include, headers):
    """Estimate include paths for single include in source file and mapped header file."""
    database = defaultdict(list)
    up_reference_count = 0
    ambiguous_paths = list()
    # Find if include in source_file could be mapped to some internal header
    # path.
    source_tokens = source.split(separator())
    include_tokens = include.split(separator())
    # Upper level references might result in multiple possible include paths.
    up_reference_count = include_tokens.count("..")
    for header_file in headers:
        header_tokens = header_file.split(separator())
        # Test if there is existing internal header matching specific include.
        if (
            header_tokens[-len(include_tokens) + up_reference_count:]
            == include_tokens[up_reference_count:]
        ):
            # Determine path to header according to specific include without
            # upper level references '..'.
            include_path_candidate = separator().join(
                header_tokens[: -len(include_tokens) + up_reference_count]
            )
            database = record_header(database, header_file)
            if up_reference_count > 0:
                ambiguous_paths = up_level_references_folders(
                    include_path_candidate, up_reference_count, header_tokens
                )
                database = record_ambiguous_paths(
                    database, ambiguous_paths, header_file
                )
            else:
                # in context record should be mandatory include paths even if
                # there is system alternative
                if not header_tokens[:-1] == source_tokens[:-1]:
                    database = record_mandatory_paths(
                        database, include_path_candidate, header_file
                    )
                else:
                    database = record_optional_paths(
                        database, include_path_candidate, header_file
                    )
        ambiguous_paths = list()
    return database


def includes_from_file(file):
    """Extract includes used in source files by regex analysis."""
    file_includes = list()
    include_regex = r'#include ["<](?P<inc_path>[^">]*)'
    if file.lower().endswith(tuple(source_types)):
        with open(file, "r", encoding="utf-8", errors="ignore") as file_data:
            for line in file_data:
                match = re.search(include_regex, line)
                if match:
                    include = match.group("inc_path")
                    file_includes.append(include)
    return sorted(file_includes)


def identify_main(file):
    """Extract includes used in source files by regex analysis."""
    # TODO: eliminate main functions in comments.
    status = False
    regex = [r'void\s*main\s*\(\s*void\s*\)\s*{',
             r'int\s*main\s*\(\s*void\s*\)\s*{',
             r'void\s*main\s*\(\s*\)\s*{',
             r'int\s*main\s*\(\s*\)\s*{',
             r'int\s*main\s*\(\s*int\s*argc\s*,\s*char\s*\*\*\s*argv\s*\)\s*{',
             r'int\s*main\s*\(\s*int\s*argc\s*,\s*char\s*\*\s*argv\s*\[\]\)\s*{']
    if file.lower().endswith(tuple([".c",".cpp"])):
        with open(file, "r+") as f:
            data = mmap.mmap(f.fileno(), 0).read().decode(encoding="utf-8",errors='ignore')
            for r in regex:
                if re.search(r, data):
                    status = True
                    break
    return status

def all_main_sources(sources):
    """List all source files with main() function."""
    sources_with_main = list()
    for file in sources:
        if identify_main(file):
            sources_with_main.append(file)
    return sources_with_main


def get_root(database):
    """Load root folder from database."""
    return list(database.keys())[0]


def get_sources(database, root):
    """Load source list from database."""
    return database[root]["source_files"]


def get_includes(database, root, source):
    """Load source file specific includes from database."""
    return database[root]["source_files"][source]["includes"]


def get_headers(database, root, source, include):
    """Load header files mapped to specific include and source file."""
    return database[root]["source_files"][source]["includes"][include]["mapped_headers"]


def get_include_paths(database, root, source, include, header):
    """Load include paths estimated for specific include, source file
    and mapped header file."""
    return database[root]["source_files"][source]["includes"][include][
        "mapped_headers"
    ][header]["include_paths"]


def get_include_types(database, root, source, include, header):
    """Load include paths type estimated for specific include, source file
    and mapped header file."""
    return database[root]["source_files"][source]["includes"][include][
        "mapped_headers"
    ][header]["path_types"][0]


def assign_types(paths, database, root, source, include, header, path):
    """Assign identified include path types for specific include path."""
    path_type = get_include_types(database, root, source, include, header)
    if "non_existing" not in path_type:
        if path not in paths.keys():
            paths[path] = {"types": []}
        if path_type not in paths[path]["types"]:
            paths[path]["types"].append(path_type)
    return paths


def paths_report(database):
    """Generate summarized include paths report per each source file."""
    database = defaultdict(list, database)
    paths = dict()
    root = get_root(database)
    for source in get_sources(database, root):
        for include in get_includes(database, root, source):
            for header in get_headers(database, root, source, include):
                for path in get_include_paths(
                        database, root, source, include, header):
                    paths = assign_types(
                        paths, database, root, source, include, header, path
                    )
    return paths


def path_types_report(paths):
    """Generate include paths classified by type report
    Generated from paths report."""
    report = defaultdict(list)
    for path in paths:
        types = paths[path]["types"]
        if "mandatory" in types:
            report["mandatory"].append(path)
        if "optional" in types and "mandatory" not in types:
            report["optional"].append(path)
        if "ambiguous" in types and "mandatory" not in types:
            report["ambiguous"].append(path)
    if "mandatory" in report.keys():
        report["mandatory"] = sorted(report["mandatory"])
    if "optional" in report.keys():
        report["optional"] = sorted(report["optional"])
    if "ambiguous" in report.keys():
        report["ambiguous"] = sorted(report["ambiguous"])
    return report


def print_list(some_list, file):
    """Print list elements in new lines."""
    print(*some_list, sep="\n", file=file)


class NoAliasDumper(yaml.Dumper):
    """Helper yml dumper to disable yml aliases.
    Workaround for known issue based on https://github.com/yaml/pyyaml/issues/103"""

    def ignore_aliases(self, data):
        return True


def record_root(database, root):
    """Save source root folder into database record."""
    database[root] = {}
    return database


def record_sources(database, sources):
    """Save source files into database record."""
    root = get_root(database)
    if sources:
        database[root]["source_files"] = {}
    for source in sources:
        database[root]["source_files"][source] = {}
    return database


def record_includes(database):
    """Save includes from single source file into database record"""
    root = get_root(database)
    for source in database[root]["source_files"]:
        database[root]["source_files"][source]["includes"] = \
            dict.fromkeys(sorted(includes_from_file(source)), 0)
    return database


def record_include_paths(database, headers):
    """Save estimated include paths mapped to each include into database record"""
    root = get_root(database)
    for source in database[root]["source_files"]:
        for include in database[root]["source_files"][source]["includes"]:
            paths = include_paths_for_include(source, include, headers)
            database[root]["source_files"][source]["includes"][include] = {
                "mapped_headers": dict(paths)
            }
    return database


def record_include_types(database, internal_include_list):
    """Save estimated include types into database record"""
    #database = defaultdict(list, database)
    root = get_root(database)
    for source in database[root]["source_files"].keys():
        for include in database[root]["source_files"][source]["includes"].keys(
        ):
            if "include_type" not in database[root]["source_files"][source]["includes"][include].keys(
            ):
                database[root]["source_files"][source]["includes"][include]["include_type"] = [
                ]
            if include in known_system_includes:
                if "system" not in database[root]["source_files"][source]["includes"][include]["include_type"]:
                    database[root]["source_files"][source]["includes"][include]["include_type"].append(
                        "system")
            if include in internal_include_list:
                if "internal" not in database[root]["source_files"][source]["includes"][include]["include_type"]:
                    database[root]["source_files"][source]["includes"][include]["include_type"].append(
                        "internal")
            else:
                if "external" not in database[root]["source_files"][source]["includes"][include]["include_type"]:
                    database[root]["source_files"][source]["includes"][include]["include_type"].append(
                        "external")
    return database


def console_print(include_paths_by_type):
    """Print estimated include paths into console."""
    if "mandatory" in include_paths_by_type.keys():
        print("\nMandatory paths:")
        print("------------------------")
        for path in include_paths_by_type["mandatory"]:
            print(path)

    if "optional" in include_paths_by_type.keys():
        print("\nOptional paths:")
        print("------------------------")
        for path in include_paths_by_type["optional"]:
            print(path)

    if "ambiguous" in include_paths_by_type.keys():
        print("\nAmbiguous paths:")
        print("------------------------")
        for path in include_paths_by_type["ambiguous"]:
            print(path)


def estimate_include_paths(root):
    """Extract data and create final reports."""
    database = defaultdict(list)

    start_time = time.time()

    now = datetime.datetime.now()
    time_now = now.strftime("%Y-%m-%d_%H-%M-%S")

    sources = source_files(root)
    headers = header_files(sources)
    includes_list = includes(sources)

    root = Path(root).as_posix()
    database = record_root(database, root)
    database = record_sources(database, sources)
    database = record_includes(database)
    database = record_include_paths(database, headers)

    internal_include_list = internal_includes(includes_list, headers)
    database = record_include_types(database, internal_include_list)

    summarized_include_paths = paths_report(database)
    include_paths_by_type = path_types_report(summarized_include_paths)

    #include_paths_by_include = include_path_by_include_report(database)

    print("\n--- INCLUDE PATH ESTIMATION ---")
    console_print(include_paths_by_type)

    target_name = os.path.basename(os.path.normpath(root))

    # Dump database objects into yml files
    file_name = '{0:s}_raw_{1:s}_include_statistics.yml'.format(
        time_now, target_name)
    with open(file_name, 'w') as report_file:
        yaml.dump(
            includes_with_count(sources),
            report_file,
            Dumper=yamlordereddictloader.Dumper,
            width=1000,
        )

    file_name = '{0:s}_raw_{1:s}_list_of_include_paths.yml'.format(
        time_now, target_name)
    with open(file_name, 'w') as report_file:
        yaml.dump(
            dict(summarized_include_paths),
            report_file,
            Dumper=NoAliasDumper,
            width=1000)

    file_name = '{0:s}_raw_{1:s}_list_of_include_path_types.yml'.format(
        time_now, target_name)
    with open(file_name, 'w') as report_file:
        yaml.dump(
            dict(include_paths_by_type),
            report_file,
            Dumper=NoAliasDumper,
            width=1000)

    file_name = '{0:s}_raw_{1:s}_full_database_record.yml'.format(
        time_now, target_name)
    with open(file_name, 'w') as report_file:
        yaml.dump(
            dict(database),
            report_file,
            Dumper=NoAliasDumper,
            width=1000)

    end_time = time.time()

    # Create verbose report
    file_name = '{0:s}_raw_{1:s}_verbose_report.txt'.format(
        time_now, target_name)
    with open(file_name, 'w') as report_file:
        print("\nExecution time: ", file=report_file)
        print("------------------------", file=report_file)
        print(str(datetime.timedelta(seconds=end_time - start_time)), file=report_file)
        print(
            "\nExecution time: ", str(
                datetime.timedelta(
                    seconds=end_time - start_time)))

        if "mandatory" in include_paths_by_type.keys():
            print("\nMandatory include paths:", file=report_file)
            print("------------------------", file=report_file)
            for path in include_paths_by_type["mandatory"]:
                print(path, file=report_file)

        if "optional" in include_paths_by_type.keys():
            print("\nOptional include paths:", file=report_file)
            print("------------------------", file=report_file)
            for path in include_paths_by_type["optional"]:
                print(path, file=report_file)

        if "ambiguous" in include_paths_by_type.keys():
            print("\nAmbiguous include paths:", file=report_file)
            print("------------------------", file=report_file)
            for path in include_paths_by_type["ambiguous"]:
                print(path, file=report_file)

        print("\nCommon include path prefix:", file=report_file)
        print("------------------------", file=report_file)
        print(
            os.path.commonprefix(
                list(
                    summarized_include_paths.keys())),
            file=report_file)

        print("\nInternal include list:", file=report_file)
        print("------------------------", file=report_file)
        print_list(internal_include_list, file=report_file)

        print("\nExternal include list:", file=report_file)
        print("------------------------", file=report_file)
        print_list(
            external_includes(
                includes_list,
                internal_include_list),
            file=report_file)

        print("\nSystem include list:", file=report_file)
        print("------------------------", file=report_file)
        print_list(system_includes(includes_list), file=report_file)

        print("\nC source file list:", file=report_file)
        print("------------------------", file=report_file)
        print_list(c_source_files(sources), file=report_file)

        print("\nHeader file list:", file=report_file)
        print("------------------------", file=report_file)
        print_list(headers, file=report_file)

        print("\nHeader folder list:", file=report_file)
        print("------------------------", file=report_file)
        print_list(header_folders(sources), file=report_file)

        print("\nC source folder list:", file=report_file)
        print("------------------------", file=report_file)
        print_list(c_source_folders(sources), file=report_file)


        sources_with_main = all_main_sources(sources)
        print("\nC and CPP sources with main():", file=report_file)
        print("------------------------", file=report_file)
        print_list(sources_with_main, file=report_file)

# --------MAIN--------
if __name__ == "__main__":
    source_root = args().root
    estimate_include_paths(source_root)

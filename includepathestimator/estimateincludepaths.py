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
from pathlib import Path, PurePath
import datetime
import time
from collections import OrderedDict, defaultdict, Counter
import yaml
import yamlordereddictloader

source_types = [".cpp", ".c", ".h", ".asm", ".s", ".S"]


def args():
    """Load arguments from command line."""
    parser = argparse.ArgumentParser(
        description="Include path estimator.",
        epilog=r"Example: py estimateincludepaths.py -r c:\GIT\mcu-sdk-2.0\middleware\lwip",
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


def source_files(source_root):
    """Get list of source files from source folder."""
    sources = list()
    for source_type in source_types:
        sources.extend(glob.glob(source_root + "/**/*" + source_type, recursive=True))
    sources = sorted(map(lambda path: PurePath(path).as_posix(), sources))
    return sources


def header_files(file_list):
    """Filter header files only from source files list."""
    return sorted(set([file for file in file_list if file.endswith(".h")]))


def c_source_files(file_list):
    """Filter c source files only from source files list."""
    return sorted(set([file for file in file_list if file.endswith(".c")]))


def header_folders(file_list):
    """List folders containing header files"""
    return sorted(
        set(map(lambda file: PurePath(file).parent.as_posix(), header_files(file_list)))
    )


def c_source_folders(file_list):
    """List folders containing c source files"""
    return sorted(
        set(
            map(
                lambda file: PurePath(file).parent.as_posix(), c_source_files(file_list)
            )
        )
    )


def includes(file_list):
    """Extract list of includes used in each source file and attach it in data structure."""
    return sorted(
        set([include for file in file_list for include in includes_from_file(file)])
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
        for file in file_list:
            file_tokens = file.split(separator())
            if file_tokens[-len(include_tokens) :] == include_tokens:
                internal_include_list.append(include)
    return sorted(set(internal_include_list))


def external_includes(include_list, internal_include_list):
    """Return external includes used in examined source files."""
    external_include_list = list(set(include_list) - set(internal_include_list))
    external_include_list = sorted(set(external_include_list))
    return external_include_list


def up_level_references_folders(
    include_path_candidate, up_reference_count, header_tokens
):
    """Get folders in scope of upper level references."""
    ambiguous_paths = list()
    subfolders = [path for path in os.scandir(include_path_candidate) if path.is_dir()]
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
    file_tokens = source.split(separator())
    include_tokens = include.split(separator())
    # Upper level references might result in multiple possible include paths.
    up_reference_count = include_tokens.count("..")
    for header_file in headers:
        header_tokens = header_file.split(separator())
        # Test if there is existing internal header matching specific include.
        if (
            header_tokens[-len(include_tokens) + up_reference_count :]
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
                if not header_tokens[:-1] == file_tokens[:-1]:
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
    file_includes = sorted(file_includes)
    return file_includes


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
                for path in get_include_paths(database, root, source, include, header):
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

def console_print(sorted_include_paths):
    # Print estimated include paths into console
    if "mandatory" in sorted_include_paths.keys():
        print("\nMandatory paths:")
        print("------------------------")
        for path in sorted_include_paths["mandatory"]:
            print(path)

    if "optional" in sorted_include_paths.keys():
        print("\nOptional paths:")
        print("------------------------")
        for path in sorted_include_paths["optional"]:
            print(path)

    if "ambiguous" in sorted_include_paths.keys():
        print("\nAmbiguous paths:")
        print("------------------------")
        for path in sorted_include_paths["ambiguous"]:
            print(path)


def estimate_include_paths(arguments):
    """Extract data and create final reports."""
    database = defaultdict(list)

    start_time = time.time()

    now = datetime.datetime.now()
    time_now = now.strftime("%Y_%m_%d_%H_%M_%S")

    sources = source_files(arguments.root)
    headers = header_files(sources)
    includes_list = includes(sources)

    root = Path(arguments.root).as_posix()
    database = record_root(database, root)
    database = record_sources(database, sources)
    database = record_includes(database)
    database = record_include_paths(database, headers)

    summarized_include_paths = paths_report(database)
    sorted_include_paths = path_types_report(summarized_include_paths)

    console_print(sorted_include_paths)

    # Dump database objects into yml files
    stream = open("%s_include_statistics.yml" % (time_now), "w")
    yaml.dump(
        includes_with_count(sources),
        stream,
        Dumper=yamlordereddictloader.Dumper,
        width=1000,
    )

    stream = open("%s_list_of_include_paths.yml" % (time_now), "w")
    yaml.dump(dict(summarized_include_paths), stream, Dumper=NoAliasDumper, width=1000)

    stream = open("%s_list_of_include_path_types.yml" % (time_now), "w")
    yaml.dump(dict(sorted_include_paths), stream, Dumper=NoAliasDumper, width=1000)

    stream = open("%s_full_database_record.yml" % (time_now), "w")
    yaml.dump(dict(database), stream, Dumper=NoAliasDumper, width=1000)

    end_time = time.time()

    # Create verbose report
    report_file = open("%s_verbose_report.txt" % (time_now), "w")

    print("\nExecution time:", file=report_file)
    print("------------------------", file=report_file)
    print(str(datetime.timedelta(seconds=end_time - start_time)), file=report_file)

    if "mandatory" in sorted_include_paths.keys():
        print("\nMandatory include paths:", file=report_file)
        print("------------------------", file=report_file)
        for path in sorted_include_paths["mandatory"]:
            print(path, file=report_file)

    if "optional" in sorted_include_paths.keys():
        print("\nOptional include paths:", file=report_file)
        print("------------------------", file=report_file)
        for path in sorted_include_paths["optional"]:
            print(path, file=report_file)

    if "ambiguous" in sorted_include_paths.keys():
        print("\nAmbiguous include paths:", file=report_file)
        print("------------------------", file=report_file)
        for path in sorted_include_paths["ambiguous"]:
            print(path, file=report_file)

    print("\nCommon include path prefix:", file=report_file)
    print("------------------------", file=report_file)
    print(os.path.commonprefix(list(summarized_include_paths.keys())), file=report_file)

    internal_include_list = internal_includes(includes_list, headers)

    print("\nInternal include list:", file=report_file)
    print("------------------------", file=report_file)
    print_list(internal_include_list, file=report_file)

    print("\nExternal include list:", file=report_file)
    print("------------------------", file=report_file)
    print_list(
        external_includes(includes_list, internal_include_list), file=report_file
    )

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

    report_file.close()


# --------MAIN--------
if __name__ == "__main__":
    estimate_include_paths(args())

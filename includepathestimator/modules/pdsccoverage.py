# Copyright 2021 NXP
# All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0

""" *.pdsc description coverage
This script percentual description coverage of source code in cmsis pack.
"""

import os
import argparse
import glob
import xml.etree.ElementTree as ET
from pathlib import Path, PurePath
import datetime
import time

from modules import estimateincludepaths as eip


def args():
    """Load arguments from command line."""
    parser = argparse.ArgumentParser(
        description="Show *.pdsc description coverage.",
        epilog=r"Example: python pdsccoverage.py -p c:\components\ARM.mbedTLS.1.6.0",
    )
    parser.add_argument(
        "-p",
        "--pack",
        action="store",
        help=" Absolute path to pack folder.",
    )
    return parser.parse_args()


def pdsc_include_paths(file_name):
    """Return standard POSIX path separator."""
    include_paths = list()
    tree = ET.parse(file_name)
    xml_root = tree.getroot()
    for file in xml_root.findall(
            "./components//component/files/file/[@category='header']"):
        include_tokens = file.attrib['name'].split(eip.separator())
        include_path_candidate = eip.separator().join(include_tokens[:-1])
        include_paths.append(include_path_candidate)
    for file in xml_root.findall(
            "./components//component/files/file/[@category='include']"):
        include_paths.append(file.attrib['name'])
    include_paths = sorted(
        set(map(lambda include_path: PurePath(include_path).as_posix(), include_paths)))
    return include_paths


def pdsc_sources(file_name):
    """Return standard POSIX path separator."""
    sources = list()
    tree = ET.parse(file_name)
    xml_root = tree.getroot()
    for file in xml_root.findall(
            "./components//component/files/file/[@category='source']"):
        sources.append(file.attrib['name'])
    sources = sorted(set(sources))
    return sources


def pdsc_components(file_name):
    """Return standard POSIX path separator."""
    components = list()
    tree = ET.parse(file_name)
    xml_root = tree.getroot()
    for file in xml_root.findall("./components//component"):
        components.append(file.attrib)
    return components


def pdsc_bundles(file_name):
    """Return standard POSIX path separator."""
    bundles = list()
    tree = ET.parse(file_name)
    xml_root = tree.getroot()
    for file in xml_root.findall("./components/bundle"):
        bundles.append(file.attrib)
    return bundles


def pdsc_examples(file_name):
    """Return standard POSIX path separator."""
    examples = list()
    tree = ET.parse(file_name)
    xml_root = tree.getroot()
    for file in xml_root.findall("./examples/example"):
        examples.append(file.attrib['name'])
    return examples


def all_headers(root_path):
    """ List files in scope of include paths. """
    sources = eip.source_files(root_path)
    headers = eip.header_files(sources)
    return headers


def all_sources(root_path):
    """ List files in scope of include paths. """
    sources = eip.source_files(root_path)
    headers = eip.header_files(sources)
    sources = set(sources) - set(headers)
    return sources


def headers_in_paths_scope(include_paths, includes_list, root_path):
    """ Compare known header files with known includes from
        source files (up-level references "../" included) and include paths defined in pdsc."""
    visible_headers_via_includes = list()
    header_files = list()
    # Identify header files visible via includes (might be relative path or "..").
    for include_path in include_paths:
        for include in includes_list:
            candidate = os.path.normpath(
                root_path +
                eip.separator() +
                include_path +
                eip.separator() +
                include)
            candidate = PurePath(candidate).as_posix()
            if Path(candidate).is_file():
                visible_headers_via_includes.append(candidate)
    # identify directly visible header files
    for include_path in include_paths:
        location = os.path.normpath(root_path + eip.separator() + include_path)
        location = PurePath(location).as_posix()
        header_files = headers_in_folder(location)
        visible_headers_via_includes.extend(header_files)
    return sorted(set(visible_headers_via_includes))


def full_path(root_path, paths):
    """Filter header files only from source files list."""
    return sorted({PurePath(root_path + eip.separator() + p).as_posix()
                  for p in paths})


def headers_in_folder(folder):
    """Get list of header files from single folder."""
    headers = list()
    headers.extend(glob.glob(folder + eip.separator() + "*.h"))
    headers = sorted(map(lambda path: PurePath(path).as_posix(), headers))
    return headers


def pdsc_in_folder(folder):
    """Get list of header files from single folder."""
    pdsc = glob.glob(folder + eip.separator() + "*.pdsc")
    return PurePath(pdsc[0]).as_posix()


def pdsc_coverage(root_path):
    """Create pdsc description coverage report."""
    visible_headers_via_includes = list()
    start_time = time.time()
    pdsc = pdsc_in_folder(root_path)
    pdsc_name = PurePath(pdsc).name
    include_paths = pdsc_include_paths(pdsc)
    headers = all_headers(root_path)
    includes_list = eip.includes(eip.source_files(root_path))
    visible_headers_via_includes = headers_in_paths_scope(
        include_paths, includes_list, root_path)
    now = datetime.datetime.now()
    time_now = now.strftime("%Y-%m-%d_%H-%M-%S")

    print("\n--- DESCRIPTION COVERAGE ---")

    report_name = '{0:s}_pdsc_{1:s}.txt'.format(time_now, pdsc_name.removesuffix('.pdsc'))
    with open(report_name, 'w') as report:

        #print("\nIncludes:", file=report)
        #print_list(includes_list, file=report)

        headers_count = len(headers)
        visible_count = len(visible_headers_via_includes)
        visibility_quotient = visible_count / headers_count * 100
        print("Number of all header files: ", headers_count, file=report)
        print(
            "Header files visible via pdsc include paths (and includes):",
            visible_count,
            file=report)
        print("Header files visibility: {0:3.1f} %".format(
            visibility_quotient), file=report)

        disk_sources = all_sources(root_path)
        sources_in_pdsc = pdsc_sources(pdsc)

        sources_count = len(disk_sources)
        pdsc_sources_count = len(sources_in_pdsc)
        sources_visibility_quotient = pdsc_sources_count / sources_count * 100
        print(
            "\nNumber of all source files: ",
            sources_count,
            file=report)
        print(
            "Sources files described in pdsc:",
            pdsc_sources_count,
            file=report)
        print("Source description coverage: {0:3.1f} %".format(
            sources_visibility_quotient), file=report)
        print("Source description coverage: {0:3.1f} %".format(
            sources_visibility_quotient))

        total_source_ch_count = sources_count + headers_count
        described_source_ch_count = visible_count + pdsc_sources_count
        ch_percentage = described_source_ch_count / total_source_ch_count * 100
        print(
            "\nCombined headers + sources description coverage: {0:3.1f} %".format(ch_percentage),
            file=report)

        components = pdsc_components(pdsc)
        print("\nComponents in *.pdsc: ", file=report)
        print("------------------------", file=report)
        eip.print_list(components, file=report)

        bundles = pdsc_bundles(pdsc)
        print("\nBundles in *.pdsc: ", file=report)
        print("------------------------", file=report)
        eip.print_list(bundles, file=report)

        examples = pdsc_examples(pdsc)
        print("\nExamples in *.pdsc: ", file=report)
        print("------------------------", file=report)
        eip.print_list(examples, file=report)

        print("\nInclude paths *.pdsc:", file=report)
        print("------------------------", file=report)
        eip.print_list(include_paths, file=report)

        print("\nHeaders visible via pdsc include paths:", file=report)
        print("------------------------", file=report)
        eip.print_list(visible_headers_via_includes, file=report)
        print("\nHeaders not visible via pdsc include paths:", file=report)
        print("------------------------", file=report)
        eip.print_list(
            sorted(
                set(headers) -
                set(visible_headers_via_includes)),
            file=report)

        expanded_pdsc_sources = full_path(root_path, sources_in_pdsc)
        print("\nSources described in pdsc:", file=report)
        print("------------------------", file=report)
        eip.print_list(expanded_pdsc_sources, file=report)
        print("\nSources not described in pdsc:", file=report)
        print("------------------------", file=report)
        eip.print_list(
            sorted(
                set(disk_sources) -
                set(expanded_pdsc_sources)),
            file=report)

    end_time = time.time()
    print(
        "\nExecution time: ", str(
            datetime.timedelta(
                seconds=end_time - start_time)))


# --------MAIN--------
if __name__ == "__main__":
    root = args().pack
    pdsc_coverage(root)

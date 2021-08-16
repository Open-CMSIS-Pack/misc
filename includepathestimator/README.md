## Installation
Tested with Python 3.9.5 on Windows 10
```
python -m venv estimator_env
estimator_env\Scripts\activate
pip install -r requirements.txt
```

## Include path estimator
This script is able to determine include paths from raw C source code.
Algorithm is based on "#include" string analysis.
Method is able to cover also up-level references "../" which could lead into multiple include paths. Cases which are not covered include various hidden includes in macros etc..

###  Execution
```
python estimateincludepaths.py -r c:\GIT\mcu-sdk-2.0\middleware\lwip
```

### Generated outputs
- verbose_report.txt
- list_of_includes.yml
- list_of_include_types.yml
- include_statistics.yml
- full_context_record.yml

### Extracted information
- Estimated mandatory include paths
- Estimated ambiguous include paths
- Estimated optional include paths
- Header file list
- Header folder list
- C source files list
- C source folder list
- Common include path prefix
- Include statistics

### Glossary
- source_code_folder - root of source code location
- source_file - '*.c', '*.h', '*.asm', '*.s', '*.S' in code source folder, (not documentation)
- include - file name or file name with path in #include directive like #include "file.h" -> file.h or #include "../folder/file.h" -> /folder/file.h
- include_file - file in #include directive without path
- internal_include -.include which could be associated with header file from source_code_folder scope
- external_include - include which could not be associated with header file from source_code_folder scope
- include_path - complementary path to include required for absolute localization of include_file. (upper level references "..", need  be taken in account)
- header_file - file with .h extension
- header_folder - folder inside source_code_folder containing at least single header_file
- source_folder - folder containing at least one source_file
- c_source_file - source file with .c extension
- c_source_folder - folder containing at least one c_source_file

### Recognized include path types
- Mandatory include paths - There is only one include path candidate, which is mandatory for build.
- Optional include paths - There is only one include path candidate which is optional for build. Compiler is able to identify header implicitly because it is in same location as source file, but for external usage include path might be necessary.
- Ambiguous include paths - There are up-level references ".." used in includes. It might resolve in list of possible include paths. User should select at least one path. Analysis of verbose reports recommended.
- Non_existing include paths - Include was mapped to existing header file, but include path cannot be determined due the missing sub folders and use of upper level references "..".

### Path management
Path analysis is transforming paths into POSIX path standard. It means script should always work with forward slashes and reports are always generated in same format for multi platform comparability.

### Known issues
Simple yml keys are denoted by "? " if length exceed 128 characters. See https://github.com/yaml/pyyaml/issues/157.

## Include path estimator

###  Execution
```
python pdsccoverage.py -p c:\TEST\ARM.mbedTLS.1.6.0
```
### Extracted information
- Description coverage [%]
- Pdsc content (components, bundles, files, examples, include paths)
- Source files description coverage [%]
- Header files visibility coverage [%]

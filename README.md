![Banner](banner.png)

# misconfig-ConfigTestCoverageAnalyzer
Analyzes configuration files to determine which parameters and features are covered by existing tests or validation rules, highlighting areas with insufficient coverage. - Focused on Check for misconfigurations in configuration files or infrastructure definitions

Only leaf parameters are counted: an intermediate key such as `database` is a container, not a parameter, while `database.port` is a parameter. A parameter counts as covered when its full dotted path or its leaf name appears in a test or rule file as a whole token, so the leaf `port` does not match the inside of the word `transport`.

## Install
`git clone https://github.com/ShadowGuardAI/misconfig-configtestcoverageanalyzer`
`pip install -r requirements.txt`

## Usage
`python3 main.py <config_file> [--test_scripts <file> ...] [--validation_rules <file> ...] [--output coverage_report.txt] [--debug]`

The report lists the test scripts and validation rule files that were read and the ones that were named but missing, so a missing input is distinguishable from a file that was read and matched nothing. A named input that does not exist makes the run exit 1 after the report is written. A report generation failure, including an unwritable output path, also exits 1. A config file with no parameters is an empty input error and exits 1 with no report.

An `--output` path that resolves to the config file under analysis is refused at exit 1 before any write, and the config file stays byte-identical.

## Parameters
- `-h`: Show help message and exit
- `config_file`: Path to the configuration file to analyze.
- `--test_scripts`: Paths to test scripts to analyze for configuration usage.
- `--validation_rules`: Paths to validation rule files to analyze for configuration coverage.
- `--output`: Path to output file to save the coverage analysis report.
- `--debug`: Enable debug logging.

## License
Copyright (c) ShadowGuardAI

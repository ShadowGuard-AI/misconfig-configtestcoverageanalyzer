import argparse
import logging
import os
import json
import re
import yaml
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def setup_argparse():
    """
    Sets up the argument parser for the CLI.
    """
    parser = argparse.ArgumentParser(
        description="Analyzes configuration files to determine test coverage of parameters and features."
    )

    parser.add_argument("config_file", help="Path to the configuration file to analyze.")
    parser.add_argument(
        "--test_scripts",
        nargs="+",
        help="Paths to test scripts (e.g., pytest files) to analyze for configuration usage.",
        required=False,
    )
    parser.add_argument(
        "--validation_rules",
        nargs="+",
        help="Paths to validation rule files (e.g., JSON schema) to analyze for configuration coverage.",
        required=False,
    )
    parser.add_argument(
        "--output",
        help="Path to output file to save the coverage analysis report.",
        default="coverage_report.txt",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging."
    )

    return parser.parse_args()


def load_config_file(config_file):
    """
    Loads a configuration file (JSON or YAML).

    Args:
        config_file (str): Path to the configuration file.

    Returns:
        dict: The configuration data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported or the content is invalid.
    """
    try:
        with open(config_file, "r") as f:
            # The type is whatever follows the last dot in the whole
            # path, so a directory with a dot in its name and an
            # extensionless file inside it borrows the directory's
            # suffix, and a file with no dot at all is judged by its own
            # name and refused as an unsupported format.
            file_extension = config_file.split(".")[-1].lower()
            if file_extension == "json":
                config_data = json.load(f)
            elif file_extension in ("yaml", "yml"):
                config_data = yaml.safe_load(f)
            else:
                raise ValueError("Unsupported configuration file format.")
        return config_data
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_file}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON file: {config_file}.  Details: {e}")
        raise ValueError(f"Invalid JSON in {config_file}") from e
    except yaml.YAMLError as e:
        logging.error(f"Error decoding YAML file: {config_file}. Details: {e}")
        raise ValueError(f"Invalid YAML in {config_file}") from e
    except Exception as e:
        logging.error(f"Error loading configuration file: {config_file}. Details: {e}")
        raise


def extract_config_parameters(config_data, prefix=""):
    """
    Recursively extracts all parameters from a configuration dictionary.

    Args:
        config_data (dict): The configuration data.
        prefix (str): The prefix for nested parameters.

    Returns:
        list: A list of parameter names.
    """
    parameters = []
    if isinstance(config_data, dict):
        for key, value in config_data.items():
            full_key = f"{prefix}{key}" if prefix else key
            if isinstance(value, (dict, list)) and value:
                # Intermediate keys are containers, not parameters.
                parameters.extend(extract_config_parameters(value, full_key + "."))
            else:
                # An empty mapping or list counts as a parameter in its own
                # right, because the container branch above requires a
                # non empty value. So a section the author left blank adds
                # one to the total and, having no leaf a test would name,
                # usually lands in the uncovered list.
                parameters.append(full_key)
    elif isinstance(config_data, list):
        for i, item in enumerate(config_data):
            if isinstance(item, (dict, list)) and item:
                parameters.extend(extract_config_parameters(item, f"{prefix}[{i}]."))
            else:
                parameters.append(f"{prefix}[{i}]")
    return parameters


def _parameter_is_referenced(param, content):
    """
    Returns True when a parameter is referenced in content as a whole
    token: either its full dotted path (for example database.port) or
    its leaf name (for example port) appearing as a delimited word.
    A raw substring is not enough, so the leaf port does not match the
    inside of the word transport.
    """
    # Coverage here means mentioned, not exercised. A parameter
    # named in a comment, a string, or a fixture counts as covered
    # by that file, and the leaf rule widens it further: one
    # mention of the word port covers every parameter whose path
    # ends in port, in however many sections the config has.
    leaf = param.split(".")[-1].split("[")[0]
    for candidate in {param, leaf}:
        if not candidate:
            continue
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(candidate) + r"(?![A-Za-z0-9_])"
        if re.search(pattern, content):
            return True
    return False


def analyze_test_scripts(test_scripts, config_parameters):
    """
    Analyzes test scripts to identify which configuration parameters are used.

    Args:
        test_scripts (list): A list of paths to test scripts.
        config_parameters (list): A list of configuration parameter names.

    Returns:
        tuple: (set of covered parameters, list of files read, list of
        named files that were missing and skipped)
    """
    covered_parameters = set()
    read_files = []
    missing_files = []
    if not test_scripts:
        return covered_parameters, read_files, missing_files
    for script in test_scripts:
        if not os.path.exists(script):
            logging.warning(f"Test script not found: {script}")
            missing_files.append(script)
            continue

        # Existence was checked above and the open is unguarded, so a
        # path that vanishes in between, or a directory handed in as
        # a test script, raises out of this function and ends the
        # whole run in main before any report is written, where a
        # missing file would only have been recorded and skipped.
        with open(script, "r") as f:
            script_content = f.read()
        read_files.append(script)

        for param in config_parameters:
            if _parameter_is_referenced(param, script_content):
                covered_parameters.add(param)

    return covered_parameters, read_files, missing_files


def analyze_validation_rules(validation_rules, config_parameters):
    """
    Analyzes validation rules to identify which configuration parameters are covered.

    Args:
        validation_rules (list): A list of paths to validation rule files (e.g., JSON schema).
        config_parameters (list): A list of configuration parameter names.

    Returns:
        tuple: (set of covered parameters, list of files read, list of
        named files that were missing and skipped)
    """
    covered_parameters = set()
    read_files = []
    missing_files = []
    if not validation_rules:
        return covered_parameters, read_files, missing_files

    for rule_file in validation_rules:
        if not os.path.exists(rule_file):
            logging.warning(f"Validation rule file not found: {rule_file}")
            missing_files.append(rule_file)
            continue

        with open(rule_file, "r") as f:
            rule_content = f.read()
        read_files.append(rule_file)

        for param in config_parameters:
            if _parameter_is_referenced(param, rule_content):
                covered_parameters.add(param)

    return covered_parameters, read_files, missing_files


def generate_coverage_report(
    config_file,
    config_parameters,
    covered_parameters_tests,
    covered_parameters_rules,
    output_file,
    test_inputs_read=None,
    test_inputs_missing=None,
    rule_inputs_read=None,
    rule_inputs_missing=None,
):
    """
    Generates a coverage report and saves it to a file.

    Args:
        config_file (str): Path to the configuration file.
        config_parameters (list): List of all configuration parameters.
        covered_parameters_tests (set): Set of parameters covered by tests.
        covered_parameters_rules (set): Set of parameters covered by validation rules.
        output_file (str): Path to the output file.

    Raises:
        Exception: Any failure while building or writing the report
        propagates to the caller, which exits non-zero. Report failures
        are never swallowed.
    """
    total_parameters = len(config_parameters)
    if total_parameters == 0:
        raise ValueError("Configuration contains no parameters to analyze.")
    covered_by_tests = len(covered_parameters_tests)
    covered_by_rules = len(covered_parameters_rules)
    covered_total = len(covered_parameters_tests.union(covered_parameters_rules))
    uncovered_parameters = set(config_parameters) - covered_parameters_tests.union(
        covered_parameters_rules
    )

    with open(output_file, "w") as f:
        f.write(f"Configuration Coverage Analysis Report\n")
        f.write(f"Configuration File: {config_file}\n\n")
        f.write("Test Scripts Read:\n")
        for path in test_inputs_read or []:
            f.write(f"- {path}\n")
        f.write("\nTest Scripts Missing (named but not read):\n")
        for path in test_inputs_missing or []:
            f.write(f"- {path}\n")
        f.write("\nValidation Rule Files Read:\n")
        for path in rule_inputs_read or []:
            f.write(f"- {path}\n")
        f.write("\nValidation Rule Files Missing (named but not read):\n")
        for path in rule_inputs_missing or []:
            f.write(f"- {path}\n")
        f.write(f"\nTotal Parameters: {total_parameters}\n")
        f.write(f"Covered by Tests: {covered_by_tests}\n")
        f.write(f"Covered by Validation Rules: {covered_by_rules}\n")
        f.write(f"Total Covered: {covered_total}\n")
        f.write(
            f"Coverage Percentage: { (covered_total / total_parameters) * 100:.2f}%\n\n"
        )
        f.write("Covered Parameters (Tests):\n")
        for param in sorted(covered_parameters_tests):
            f.write(f"- {param}\n")
        f.write("\nCovered Parameters (Validation Rules):\n")
        for param in sorted(covered_parameters_rules):
            f.write(f"- {param}\n")
        f.write("\nUncovered Parameters:\n")
        for param in sorted(uncovered_parameters):
            f.write(f"- {param}\n")

    logging.info(f"Coverage report saved to: {output_file}")


def main():
    """
    Main function to execute the configuration test coverage analyzer.
    """
    args = setup_argparse()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Settled ruling: an output path that resolves to the config file
    # under analysis is refused before any read or write, and the
    # input stays byte-identical.
    if Path(args.output).resolve() == Path(args.config_file).resolve():
        logging.error(
            f"Refusing to write the report to the configuration file under analysis: {args.output}"
        )
        sys.exit(1)

    try:
        config_data = load_config_file(args.config_file)
        config_parameters = extract_config_parameters(config_data)
        logging.debug(f"Extracted config parameters: {config_parameters}")

        if not config_parameters:
            logging.error(
                f"Configuration file contains no parameters to analyze (empty input): {args.config_file}"
            )
            sys.exit(1)

        covered_parameters_tests, test_read, test_missing = analyze_test_scripts(
            args.test_scripts, config_parameters
        )
        logging.debug(f"Covered parameters by tests: {covered_parameters_tests}")

        covered_parameters_rules, rule_read, rule_missing = analyze_validation_rules(
            args.validation_rules, config_parameters
        )
        logging.debug(f"Covered parameters by rules: {covered_parameters_rules}")

        # The report is written before the missing files verdict in
        # main, and the default output name lands in whatever
        # directory the tool was run from. Only the config file is
        # protected from being overwritten, by the check at the top
        # of main; a test script named as the output would be
        # replaced by the report without a word.
        generate_coverage_report(
            args.config_file,
            config_parameters,
            covered_parameters_tests,
            covered_parameters_rules,
            args.output,
            test_inputs_read=test_read,
            test_inputs_missing=test_missing,
            rule_inputs_read=rule_read,
            rule_inputs_missing=rule_missing,
        )

        if test_missing or rule_missing:
            logging.error(
                "One or more named test script or validation rule files did not exist and were not read."
            )
            sys.exit(1)

    except FileNotFoundError:
        sys.exit(1)  # Exit with error code
    except ValueError:
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
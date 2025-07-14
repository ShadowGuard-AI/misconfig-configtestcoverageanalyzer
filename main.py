import argparse
import logging
import os
import json
import yaml
import subprocess
import sys

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
            parameters.append(full_key)
            parameters.extend(extract_config_parameters(value, full_key + "."))
    elif isinstance(config_data, list):
        for i, item in enumerate(config_data):
            parameters.extend(extract_config_parameters(item, f"{prefix}[{i}]."))
    return parameters


def analyze_test_scripts(test_scripts, config_parameters):
    """
    Analyzes test scripts to identify which configuration parameters are used.

    Args:
        test_scripts (list): A list of paths to test scripts.
        config_parameters (list): A list of configuration parameter names.

    Returns:
        set: A set of covered configuration parameters.
    """
    covered_parameters = set()
    if not test_scripts:
        return covered_parameters
    try:
        for script in test_scripts:
            if not os.path.exists(script):
                logging.warning(f"Test script not found: {script}")
                continue

            with open(script, "r") as f:
                script_content = f.read()

            for param in config_parameters:
                if param in script_content:
                    covered_parameters.add(param)

    except Exception as e:
        logging.error(f"Error analyzing test scripts: {e}")
    return covered_parameters


def analyze_validation_rules(validation_rules, config_parameters):
    """
    Analyzes validation rules to identify which configuration parameters are covered.

    Args:
        validation_rules (list): A list of paths to validation rule files (e.g., JSON schema).
        config_parameters (list): A list of configuration parameter names.

    Returns:
        set: A set of covered configuration parameters.
    """
    covered_parameters = set()
    if not validation_rules:
        return covered_parameters

    try:
        for rule_file in validation_rules:
            if not os.path.exists(rule_file):
                logging.warning(f"Validation rule file not found: {rule_file}")
                continue

            with open(rule_file, "r") as f:
                rule_content = f.read()

            for param in config_parameters:
                if param in rule_content:
                    covered_parameters.add(param)

    except Exception as e:
        logging.error(f"Error analyzing validation rules: {e}")

    return covered_parameters


def generate_coverage_report(
    config_file,
    config_parameters,
    covered_parameters_tests,
    covered_parameters_rules,
    output_file,
):
    """
    Generates a coverage report and saves it to a file.

    Args:
        config_file (str): Path to the configuration file.
        config_parameters (list): List of all configuration parameters.
        covered_parameters_tests (set): Set of parameters covered by tests.
        covered_parameters_rules (set): Set of parameters covered by validation rules.
        output_file (str): Path to the output file.
    """
    try:
        total_parameters = len(config_parameters)
        covered_by_tests = len(covered_parameters_tests)
        covered_by_rules = len(covered_parameters_rules)
        covered_total = len(covered_parameters_tests.union(covered_parameters_rules))
        uncovered_parameters = set(config_parameters) - covered_parameters_tests.union(
            covered_parameters_rules
        )

        with open(output_file, "w") as f:
            f.write(f"Configuration Coverage Analysis Report\n")
            f.write(f"Configuration File: {config_file}\n\n")
            f.write(f"Total Parameters: {total_parameters}\n")
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

    except Exception as e:
        logging.error(f"Error generating coverage report: {e}")


def main():
    """
    Main function to execute the configuration test coverage analyzer.
    """
    args = setup_argparse()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        config_data = load_config_file(args.config_file)
        config_parameters = extract_config_parameters(config_data)
        logging.debug(f"Extracted config parameters: {config_parameters}")

        covered_parameters_tests = analyze_test_scripts(
            args.test_scripts, config_parameters
        )
        logging.debug(f"Covered parameters by tests: {covered_parameters_tests}")

        covered_parameters_rules = analyze_validation_rules(
            args.validation_rules, config_parameters
        )
        logging.debug(f"Covered parameters by rules: {covered_parameters_rules}")

        generate_coverage_report(
            args.config_file,
            config_parameters,
            covered_parameters_tests,
            covered_parameters_rules,
            args.output,
        )

    except FileNotFoundError:
        sys.exit(1)  # Exit with error code
    except ValueError:
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
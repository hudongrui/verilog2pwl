#!/usr/bin/python3
# -*- coding: utf-8 -*-
##########################
# Description:
#   Helper functions
##########################
import re
import sys
import subprocess
from typing import Tuple, Optional
from colorlog import getLogger
from sympy import sympify
from pyverilog.vparser.ast import ModuleDef
from pyverilog.vparser.parser import parse as vparse

logger = getLogger("main")

MODULE_REGEX = "^module (\w+)"

def eval_expr(e, base=None, unit=None):
    """Evaluate expression string & remove trailing zeroes."""
    result = sympify(e)

    if unit:
        _args = []
        for arg in str(result).split():
            try:
                float(arg)
            except ValueError:
                _args.append(arg)
                pass
            else:
                _args.append(f"{float(arg * int(base))}{unit}")

        return " ".join(_args)

    else:
        return result

def run_command(cmd: str, shell: bool = True, timeout: Optional[float] = None) -> Tuple[int, str, str]:
    """Execute a command and return the exit code, stdout, and stderr.

    Args:
        cmd: Command string to execute
        shell: Whether to execute in the shell (default: True)
        timeout: Maximum time to wait for command completion in seconds (optional)

    Returns:
        Tuple of (return_code, stdout_str, stderr_str)
    """
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return (
            result.returncode,
            result.stdout,
            result.stderr
        )
    except subprocess.TimeoutExpired:
        return (-1, "", "Command timed out")
    except Exception as e:
        return (-2, "", f"Error executing command: {str(e)}")

def parse_ast(input_files: list):
    """
    Parse input Verilog modules and return Abstract Syntax Trree & Top Module name.
    """
    ast, _ = vparse(input_files)

    modules = []

    for child in ast.children():
        for instance in child.definitions:
            if isinstance(instance, ModuleDef):
                modules.append({
                    'module': instance.name,
                    'lineno': instance.lineno
                })

    logger.info(modules)
    if modules:
        return ast, modules[-1]['module']  # Return the last module as MAIN. NOTE: Test this

    raise ValueError("No module found in the Verilog file")

def safe_get_module_top(input_file: str):
    """
    Temporary workaround.

    Read input verilog file line by line.
    """
    module_top = None

    with open(input_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if re.search(MODULE_REGEX, line):
                module_top, = re.search(MODULE_REGEX, line).groups()

    if not module_top:
        logger.fatal(f"Failed to parse module top. Exit.")
        sys.exit(-1)

    return module_top
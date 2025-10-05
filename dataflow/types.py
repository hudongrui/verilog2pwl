#!/usr/bin/python3
# -*- coding: utf-8 -*-
#################################
# File Name   : types.py
# Author      : dongruihu
# Created at  : 2025-08-19 17:35:52
# Description:
#   Dataclass for parsed signals
#################################
import re
import sys
from logging import getLogger
from typing import Tuple, Dict, List
import numpy as np
from dataclasses import dataclass, field
from .helper import eval_expr

logger = getLogger('main')

TIMESCALE_ROUNDING = 3


@dataclass
class TimeScale:
    base_num: int = 1  # 1ps
    base_unit: str = 'ps'

    def __post_init__(self):
        self._unit_conversion = {
            'ms': 1e3,
            'us': 1e6,
            'ns': 1e9,
            'ps': 1e12
        }

    def __repr__(self):
        return f"{self.base_num}{self.base_unit}"

    def convert_to(self, timestamp: int, unit: str='ns'):
        _mul = self._unit_conversion.get(unit) / self._unit_conversion.get(self.base_unit)
        _value = round(float(timestamp * _mul), TIMESCALE_ROUNDING)
        return _value


@dataclass
class Register:
    name: str
    width: int = 1  # Bus, such as: output reg [7:0] RTSEL (verilog)
    dim: int = 0  # 2-D array, such as: output reg [8:0] WEM[31:0]  (verilog)

    def __post_init__(self):
        self.data = np.zeros(self.width)  # Perhaps not used.
        self.timing_assignments: Dict[float, np.ndarray] = {}  # Default unit: 1ns
        self.export_pwl_safe = True

    def tag(self, x_state: bool=False):
        self.export_pwl_safe = not x_state

    def __repr__(self) -> str:
        if self.width == 1:
            return self.name
        else:
            return f'{self.name}[{self.width - 1}:0]'

    def __str__(self):
        return self.__repr__()

    def update(self, timestamp: int, value: int):
        # data = self.str2bit_array(value)

        # # Pad the values
        # if len(data) < self.width:
        #     # Pad w/ zeros if necessary
        #     data = np.pad(data, (self.width - len(data), 0), 'constant')
        bit_value = self.int2bit_array(value)

        # Update timing assignment
        logger.debug(f"Update assignment for {self.name:<20} | {timestamp}: {''.join(bit_value.astype(str))}")
        self.timing_assignments[timestamp] = bit_value
        self.data = bit_value

    def int2bit_array(self, value: int):
        """
        Convert integer to bit_array, from MSB -> LSB.
        """
        if value.bit_length() > self.width:
            raise ValueError(f"Value {value} requires more than {self.width} bits.")

        bits = np.zeros(self.width, dtype=np.int8)
        for i in range(self.width):
            bits[self.width - 1 - i] = (value >> i) & 1

        return bits

    @staticmethod
    def str2bit_array(value_str: str):
        """
        b1110111 -> numpy.array
        """
        regex = r'^b?(\d+)'
        if not re.match(regex, value_str):
            raise ValueError("Failed to convert string to bit_array")

        else:
            binary_str, = re.match(regex, value_str).groups()

            return np.array([int(s) for s in binary_str])

    def generate_piecewise_linear(self, timescale: TimeScale, expr: dict) -> str:
        if not self.export_pwl_safe:
            logger.info(f"Skipging piece-wise linear for x-state signal: {self.__str__()}")
            return ""

        lines = ""
        for data_idx, x in np.ndenumerate(self.data):
            if len(data_idx) > 1:  # 2-D Vector - TODO: Test 2-D Vector
                n, m = data_idx
                pwl_name = f"{self.name}{self.dim - 1 - n}[{self.width - 1 - m}]"  # MSB -> LSB
            elif len(data_idx) == 1 and self.width > 1:  # 1-D Bus
                m, = data_idx
                # NOTE: index is reversed as MSB/LSB
                bit_idx = self.width - 1 - m  # Convert MSB -> LSB
                pwl_name = f"{self.name}[{bit_idx}]"
            else:
                pwl_name = f"{self.name}"

            line = f"V{pwl_name} {pwl_name} 0 pwl("

            _prev = 'na'  # Previous value
            for idx, (_timestamp, bit_value) in enumerate(self.timing_assignments.items()):
                # if len(data_idx) > 1:  # 2-D Vector - NOT USED
                #     (n, m) = data_idx
                #     crnt_v = 'vvdd' if v[n][m] else '0'
                crnt_v = 'vvdd' if bit_value[data_idx] else '0'

                if _prev == 'na':  # @ t0, use initial value
                    line += f"0 {crnt_v}\n+"
                elif _prev != crnt_v:  # NOTE: signal previous value, if changes, add a 't + trf' clause
                    rf_identifier = 'tcrf' if self.name == 'CLK' else 'trf'
                    t = timescale.convert_to(_timestamp, unit='ns') # This returns a float # TODO: Use global unit
                    t_expr = eval_expr(t, base=1, unit='ns')

                    if expr.get(rf_identifier) == 0:
                        t_rf = eval_expr(f'{t} + {rf_identifier}', base=1, unit='ns')
                        line += f"'{t_expr}' {_prev} '{t_rf}' {crnt_v} "
                    else:
                        line += f"'{t_expr}' {crnt_v} "

                else:
                    pass  # Skip on no-value update.

                _prev = crnt_v
            line += ')\n\n'
            lines += line

        return lines

@dataclass
class Wire(Register):
    name: str
    width: int = 1  # Bus, such as: output reg [7:0] RTSEL (verilog)
    dim: int = 0  # 2-D array, such as: output reg [8:0] WEM[31:0]  (verilog)

    def __post_init__(self):
        super().__post_init__()

    def __repr__(self) -> str:
        if self.width == 1:
            return self.name
        else:
            return f'{self.name}[{self.width - 1}:0]'

    def __str__(self):
        return self.__repr__()

@dataclass
class Module:  # scope definition w/ $scope & $upscope
    name: str
    variables: Dict[str, Register] = field(default_factory=dict)  # Tuple[str, (reg/wire)

    def add_signal(self, _identifier: str, reg: Register):
        self.variables[_identifier] = reg

    def export_pwl(self, timescale: TimeScale, expr: dict):
        logger.info(f"\tmodule: {self.name} | vars: {self.variables.keys()}")
        data = ''
        for _identifier, reg in self.variables.items():
            if isinstance(reg, Register):
                logger.info(f'Generate piece-wise linear for {reg}')
                data += reg.generate_piecewise_linear(timescale=timescale, expr=expr) + '\n'
            elif isinstance(reg, Wire):
                logger.info(f'Generate piece-wise linear for wire {reg}')
                data += reg.generate_piecewise_linear(timescale=timescale, expr=expr) + '\n'
            else:
                logger.fatal("Un-reachable code.")
        return data

@dataclass
class VCDModule:
    date: str = ''
    version: str = ''
    timescale: TimeScale = None
    module: Module = None  # Top module
    current_module: Module = None
    _shadow_modules: List[Module] = field(default_factory=list)
    signals: List[Register] = field(default_factory=list)

    def __post_init__(self):
        self._sig_map = {}  # For unique identifier mapping, such as ! -> AA, " -> AB

    def add_reg(self, reg: Register, _identifier: str) -> None:
        self._sig_map[_identifier] = reg.name
        # logger.debug(f"module: {self.current_module.name} | add_signal: {reg.name}")
        self.current_module.add_signal(_identifier, reg)
        self.signals.append(reg)

    def add_wire(self, wire: Wire, _identifier: str) -> None:
        self._sig_map[_identifier] = wire.name
        self.current_module.add_signal(_identifier, wire)
        self.signals.append(wire)

    def update_module(self, scope: str):
        logger.debug(f'Adding new scope: {scope}')
        if not self.module:
            self.module = Module(scope)
            self.current_module = self.module
        elif self.module.name != scope:
            m = Module(scope)
            self._shadow_modules.append(m)
            self.current_module = m
        else:
            logger.warning(f"Repeated scope entry: {scope}. Please check vcd file.")

    def is_reg_top_module(self, ident: str) -> bool:
        return ident in self.module.variables.keys()

    def update_timing_assignment(self, timestamp: int, _identifier: str, value: int, full: bool = False):
        # Skip intermediary signals.
        if not full and not self.is_reg_top_module(_identifier):
            return

        time_value = self.timescale.convert_to(timestamp, 'ns')  # TODO:
        _reg = self.module.variables.get(_identifier)

        if not _reg:
            logger.error(f'un-recognized identifier: {_identifier}, not top_module: {self.module.variables.keys()}')
            logger.error(f'current module: {self.current_module}')
            sys.exit(-1)

        # NOTE: Check if value is integer, if 'x' & 'z' then ignore timing assignment, FOR NOW.
        if isinstance(value, str):
            logger.warning(f"\t{_reg}: Skipping ambiguous signal value definition, during update timing assignment: {value}")
            _reg.tag(x_state=True)
            return

        _reg.update(timestamp=timestamp, value=value)
        logger.debug(f"Setting {_reg.name} to '{value}' at time: {time_value}")

    def export_pwl(self, output_filepath: str, expr: dict) -> None:
        # NOTE: Defaults to export top pwl only.
        with open(output_filepath, 'w') as f:
            f.write(self.module.export_pwl(timescale=self.timescale, expr=expr))

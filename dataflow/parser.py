#!/usr/bin/python3
# -*- coding: utf-8 -*-
################################
# File Name   : parser
# Author      : dongruihu
# Created at  : 2025-08-19 17:35:52
# Description:
#   Parse VCD file to dataflow
#################################
from logging import getLogger
from io import StringIO
from pyvcd.reader import tokenize, TokenKind, VCDParseError
from pyvcd.common import VarType
from dataflow.types import *

logger = getLogger('main')

class VCDParser:
    def __init__(self):
        self._iter = None
        self.expr = None  # For special expression/value mapping
        self.t = None  # Tokenizer

    def parse(self, fh: StringIO):
        try:
            self.t = tokenize(fh)
            return self._parse_group()
        except AssertionError as e:
            logger.error(f'Parser Error. {e}', exc_info=True)
            return None

    def set_expr(self, expr: dict):
        self.expr = expr

    def _parse_group(self, top: VCDModule = None, scope: str = None, full: bool = False) -> VCDModule:
        """
        @params:
        top:  top module <class.VCDModule>
        scope: current scope in '$scope <ident> CURRENT_SCOPE $end'
        full: record timing assignment for all signals in all scopes, including intermediary signals.
        """
        if not top:
            top = VCDModule()

        _timestamp = 0

        try:
            while True:
                _toc = next(self.t)

                if _toc.kind == TokenKind.DATE:
                    top.date = _toc.data

                elif _toc.kind == TokenKind.VERSION:
                    top.version = _toc.data

                elif _toc.kind == TokenKind.TIMESCALE:
                    logger.info(f'Setting timescale: {_toc.data}')
                    _base, _unit = tuple(str(_toc.data).split())
                    top.timescale = TimeScale(
                        base_num=int(_base),
                        base_unit=_unit
                    )
                elif _toc.kind == TokenKind.SCOPE:
                    # Enter a new scope
                    scope = _toc.data.ident
                    logger.debug(f'Enter scope: {scope}')
                    top.update_module(scope)
                    # Create or switch to new scope

                elif _toc.kind == TokenKind.UPSCOPE:  # $upscope
                    # 20250928 NOTE: Only export top_module
                    logger.info(f'Using reg: {", ".join(str(s) for s in top.signals)}')
                    logger.debug(f'Leaving scope: {scope}')
                    scope = None

                elif _toc.kind == TokenKind.VAR:
                    # Define a new signal/variable
                    reg_decl = _toc.data  # VarDecl(VarType.reg)
                    name = reg_decl.reference
                    width = reg_decl.size
                    identifier = reg_decl.id_code

                    _type = str(reg_decl.type_)  # reg or wire
                    if _type == str(VarType.reg):
                        # Create and add signal
                        reg = Register(name=name, width=width)
                        logger.debug(f'  declare reg: {identifier} -> {reg} | scope: {scope}')
                        top.add_reg(reg, identifier)
                    elif _type == str(VarType.wire):
                        # Add wire. un-used for now.
                        wire = Wire(name=name, width=width)
                        logger.debug(f' declare wire: {identifier} -> {wire} | scope: {scope}')
                        top.add_wire(wire, identifier)

                elif _toc.kind == TokenKind.CHANGE_TIME:
                    _timestamp = _toc.data
                    logger.debug(f'Update timestamp: {_timestamp} {top.timescale.base_unit}')

                elif _toc.kind in (TokenKind.CHANGE_SCALAR, TokenKind.CHANGE_VECTOR):
                    identifier = _toc.data.id_code
                    value = _toc.data.value

                    if isinstance(value, str):
                        if 'x' in value or 'z' in value:
                            logger.debug(f"Un-supported data type: '{value}', ignored due to intermediary output.")
                        else:
                            logger.debug(f"\tconverting string '{value}'  to int '{int(value)}'")
                            value = int(value)
                    top.update_timing_assignment(_timestamp, identifier, value, full=full)

                elif _toc.kind == TokenKind.CHANGE_TIME:
                    _timestamp = _toc.data
                    logger.debug(f'[dumpvar] Update timestamp: {_timestamp} {top.timescale.base_unit}')

                elif _toc.kind == TokenKind.DUMPVAR:
                    continue

        except StopIteration:
            return top

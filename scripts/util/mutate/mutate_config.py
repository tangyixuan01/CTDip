#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
#define SCHAR_MIN -128
#define SCHAR_MAX 127
#define CHAR_MIN -128
#define CHAR_MAX 127
#define UCHAR_MAX 255
#define SHRT_MIN -32768
#define SHRT_MAX 32767
#define USHRT_MAX 65535
#define INT_MIN -2147483648
#define INT_MAX 2147483647
#define UINT_MAX 4294967295U
#define LONG_MIN -9223372036854775808L
#define LONG_MAX 9223372036854775807L
#define ULONG_MAX 18446744073709551615UL
#define RAND_MAX 32767
"""

TYPE_DECL_2_SIMPLE_TYPE = {
    'char': 'char', 'unsigned char': 'uchar', 'short': 'short', 'unsigned short': 'ushort',
    'int': 'int', 'unsigned int': 'uint', 'long': 'long', 'unsigned long': 'ulong',
    'long long': 'long', 'unsigned long long': 'ulong', 'long long int': 'long',
    'unsigned long long int': 'ulong', '_Bool': 'bool', 'bool': 'bool', 'size_t': 'bool',
    'int8_t': 'char', 'uint8_t': 'uchar', 'int16_t': 'short', 'uint16_t': 'ushort',
    'int32_t': 'int', 'uint32_t': 'uint', 'int64_t': 'long', 'uint64_t': 'ulong',
    'double': 'double', 'float': 'float', 'long double': 'double', 'unsigned': 'uint',
    'signed': 'int', 'long int': 'long', 'unsigned int': 'uint', 'short int': 'short',
    'signed char': 'char'
}

# bool, char, uchar, short, ushort, int, uint, long, ulong
TYPE_2_RANGE = {
    'bool': (0, 1), 
    'char': (-128, 127), 'uchar': (0, 255), 
    'short': (-32768, 32767), 'ushort': (0, 65535), 
    'int': (-2147483648, 2147483647), 'uint': (0, 4294967295),
    'long': (-9223372036854775807, 9223372036854775807), 'ulong': (0, 18446744073709551615),
    'double': (-1.7976931348623157e+308, 1.7976931348623157e+308), 'float': (-3.4028234663852886e+38, 3.4028234663852886e+38)
}

"""
_Bool
signed char
unsigned char
short
unsigned short
int
unsigned int
long long int
unsigned long long int
"""
TYPE_2_NEW_TYPE = {
    '_Bool': ['signed char', 'unsigned char', 'short', 'unsigned short', 'int', 'unsigned int', 'long long int', 'unsigned long long int'],
    'signed char': ['short', 'int', 'long long int'],
    'unsigned char': ['unsigned short', 'unsigned int', 'unsigned long long int'],
    'short': ['int', 'long long int'],
    'unsigned short': ['unsigned int', 'unsigned long long int'],
    'int': ['long long int'],
    'unsigned int': ['unsigned long long int']
}

from pycparser import c_ast
NODE_TYPE_2_AST_TYPE = {
    'for': c_ast.For,
    'if': c_ast.If,
    'while': c_ast.While,
    'assignment': c_ast.Assignment,
    'compound': c_ast.Compound,
    'return': c_ast.Return
}

BLACKLIST_FILE_PATH = '/home/workplace/compiler_testing/scripts/util/mutate/newblacklist.txt'

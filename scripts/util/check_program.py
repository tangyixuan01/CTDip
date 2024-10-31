#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import re
import sys
import datetime
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import common
from common import run_cmd
from util.sys_util import *
from util.config import *
from util.tools import *


check_timeout = 30              # 60s
compiler_mem_limit = 10000000   # 10 Gb

sanitizer2paramaters = {
    # 'MSAN': '-fsanitize=memory -fno-omit-frame-pointer -g -O0 -w',
    # 'ASAN': '-fsanitize=address -O0 -w -fno-omit-frame-pointer -g',
    # 'UBSAN': '-fsanitize=undefined -O1 -w -lgcc_s --rtlib=compiler-rt -g'
    'MSAN': '-fsanitize=memory -Werror=uninitialized -fno-omit-frame-pointer  -g -w -I' + CSMITH_INCLUDE_DIR,
    'ASAN': '-fsanitize=address -Werror=uninitialized -fno-omit-frame-pointer -g -w -I' + CSMITH_INCLUDE_DIR,
    'UBSAN': '-fsanitize=undefined -Werror=uninitialized -lgcc_s --rtlib=compiler-rt -g -w -I' + CSMITH_INCLUDE_DIR
}

mutation2count = {}

sanitizer_error_msg = set([
    'runtime error',
    'AddressSanitizer',
    'MemorySanitizer',
    'UndefinedBehaviorSanitizer'
])

def build_compile_fail_log(log_file_path, seed, tag, mutation_operator_label, compile_cmd, compie_err_output):
    with open(log_file_path, 'w') as log:
        log.write("YARPGEN version: " + common.yarpgen_version_str + "\n")
        log.write("Seed: " + str(seed) + "\n")
        log.write("Time: " + datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S') + "\n")
        log.write("Language standard: " + common.get_standard() + "\n")
        log.write("Type: " + tag + "\n")
        # ^ mutation operator label
        log.write("Mutation operator label: " + mutation_operator_label + "\n")
        log.write("\n\n")

        log.write("Compile command: ==================================\n")
        log.write(compile_cmd + "\n")
        log.write("===================================================\n")
        log.write("Compile error message: ============================\n")
        log.write(str(compie_err_output) + "\n")
        log.write("===================================================\n")


class Run_Sanitizer():
    clang_compile = 'clang-18'
    gcc_compile = '/home/jwzeng/compilers/gcc-trunk-20230829/bin/gcc'

    def __init__(self, original_compiler, sanitizer, seed):
        self.original_compiler = original_compiler
        self.sanitizer = sanitizer
        self.seed = str(seed)


def check_program_by_sanitizer_with_single_threaded(clang_compiler, sanitizer, program_file_path, tmp_dir, proc_num=-1, seed=-1, 
                               lock=None, mutation_operator_label='', local_timeout=-1):
    global sanitizer2paramaters
    check_cmd = [clang_compiler, sanitizer2paramaters[sanitizer]] + program_file_path

    if local_timeout == -1:
        ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_command(check_cmd, check_timeout, proc_num, compiler_mem_limit)
    else:
        ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_command(check_cmd, local_timeout, proc_num, compiler_mem_limit)     

    with open(os.path.join(tmp_dir, 'sanitizer-' + str(seed) + '.log'), 'a+') as f:
        f.write(str(check_cmd) + '\n')
        f.write(f'>> seed: {seed} - compile\n')
        f.write(f'@@ sanitizer: {sanitizer}\n')
        f.write(f'@@ ret_code: {ret_code}\n')
        f.write(f'@@ output: {output.decode().strip()}\n')
        f.write(f'@@ err_output: {err_output.decode().strip()}\n')
        f.write(f'@@ is_time_expired: {is_time_expired}\n')
        f.write(f'@@ elapsed_time: {elapsed_time}\n')
        f.write('\n')
    if ret_code != 0 or is_time_expired or not os.path.exists(os.path.join(tmp_dir, "a.out")):
        mutation2count[mutation_operator_label] = mutation2count.get(mutation_operator_label, 0) + 1
        return False
    else:
        if local_timeout == -1:
            ret_code, output, err_output, is_time_expired, elapsed_time = \
                run_command([os.path.join(tmp_dir, 'a.out')], check_timeout, proc_num)
        else:
            ret_code, output, err_output, is_time_expired, elapsed_time = \
                run_command([os.path.join(tmp_dir, 'a.out')], local_timeout, proc_num)     
        with open(os.path.join(tmp_dir, 'sanitizer-' + str(seed) + '.log'), 'a+') as f:
            f.write(f'>> seed: {seed} - run\n')
            f.write(f'@@ sanitizer: {sanitizer}\n')
            f.write(f'@@ ret_code: {ret_code}\n')
            f.write(f'@@ output: {output.decode().strip()}\n')
            f.write(f'@@ err_output: {err_output.decode().strip()}\n')
            f.write(f'@@ is_time_expired: {is_time_expired}\n')
            f.write(f'@@ elapsed_time: {elapsed_time}\n')
            f.write('\n')

        if ret_code != 0 or is_time_expired or err_output.decode().strip() != '':
            return False
        return True
    

def check_program_by_sanitizer(clang_compiler, sanitizer, program_file_path, tmp_dir, proc_num=-1, seed=-1, 
                               lock=None, mutation_operator_label=''):
    global sanitizer2paramaters
    check_cmd = [clang_compiler, sanitizer2paramaters[sanitizer]] + program_file_path
    ret_code, output, err_output, is_time_expired, elapsed_time = \
        run_cmd(check_cmd, check_timeout, proc_num, compiler_mem_limit)

    if ret_code != 0 or is_time_expired or not os.path.exists(os.path.join(tmp_dir, "a.out")):

        return False
    else:
        ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_cmd([os.path.join(tmp_dir, 'a.out')], check_timeout, proc_num)

        if ret_code != 0 or is_time_expired or err_output.decode().strip() != '':

            return False
        return True
    

def grep_crash_info(output_log_file_path, proc_num=-1):
    grep_cmd = [r'grep -e"../gcc-source/gcc/" -e"assert" -e" diagnostic msg" -e"error: unable to execute command: Aborted" -e"Assertion" -e"LLVM ERROR" -e"Error: " -e"ERROR:" -e"BUG" -e"bug" -e"Bug" -e"Please" -e"please" -e"PLEASE" -e"Please" -e"internal compiler error:" -e" ============ test " -e"CPU time limit" -e"clang: error:" -e"unable to execute command: File size limit exceeded" -e"generic_simplify_BIT_NOT_EXPR" -e"diagnostic msg" -e"error: clang frontend command failed with exit code" -e"failed." -e": Assertion"', output_log_file_path, r' | grep -ve"bugger(" -ve"copysign_bug" -ve"==ERROR: MemorySanitizer: " -ve"==ERROR: AddressSanitizer: " -ve"5-testing_all.sh" -ve"clang: error: linker command failed with exit code 1" -ve "debug" -ve "u32 bug " -ve "In function ‘bug’:" -ve"Please use" -ve"bug when they were" -ve"This tests for a bug in regstack" -ve"int showbug" -ve"unsigned bug " -ve"Bug in reorg.c" -ve"This bug exists in " -ve"had a bug that causes the final" -ve"If some target has a Max alignment less than 32" | grep -B1 -e"diagnostic msg" -e"generic_simplify_BIT_NOT_EXPR" -e"error: unable to execute command: Aborted" -e"Assertion" -e"LLVM ERROR" -e"Error: " -e"ERROR:" -e"BUG" -e"bug" -e"Bug" -e"Please" -e"please" -e"PLEASE" -e"Please" -e"internal compiler error:" -e"CPU time limit" -e"unable to execute command: File size limit exceeded"']
    ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_cmd(grep_cmd, check_timeout, proc_num, compiler_mem_limit)

    
    # ret_code, output, err_output, is_time_expired, elapsed_time = \
    #     run_command(grep_cmd, check_timeout, proc_num, compiler_mem_limit)
    # print('grep output:', output)
    if ret_code == 0 and output != '':
        return True
    return False


COMPILER2REAL = {
    'clang': '/home/jwzeng/compilers/llvm/llvm-16.0.0/bin/clang -Werror=uninitialized',
    'clang-c': '/home/jwzeng/compilers/llvm/llvm-16.0.0/bin/clang -Werror=uninitialized -c',
    'gcc': '/home/jwzeng/compilers/gcc/gcc-13.1.0/bin/gcc  -Werror=uninitialized',
    'gcc-c': '/home/jwzeng/compilers/gcc/gcc-13.1.0/bin/gcc  -Werror=uninitialized -c',
    # 'tcc': 'tcc',
    # 'tcc-c': 'tcc -c',
    'icx': 'icx -fPIC -mcmodel=large -w -fopenmp-simd -mllvm -vec-threshold=0',
    'icx-c': 'icx -fPIC -mcmodel=large -w -fopenmp-simd -mllvm -vec-threshold=0 -c',
}
opts = ['-O0', '-O1', '-O2', '-O3', '-Os']
def check_compiler_ICE(compiler, program_file_path, tmp_dir, proc_num=-1, seed=-1,
                          lock=None, mutation_operator_label=''):
    for opt in opts:
        check_cmd = [COMPILER2REAL[compiler], opt, '-w', '-I' + CSMITH_INCLUDE_DIR]\
              + program_file_path + ['> ' + os.path.join(tmp_dir, 'ice.log') + ' 2>&1']
        ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_cmd(check_cmd, check_timeout, proc_num, compiler_mem_limit)
        
        

    
        err_output = str(err_output, "utf-8").strip()
        if ret_code != 0 or is_time_expired or err_output != '':
            is_crash = grep_crash_info(os.path.join(tmp_dir, 'ice.log'), proc_num)
            if is_crash or is_time_expired:
                error_state = 'crash' if is_crash else 'hang'
                file_list = copy.deepcopy(program_file_path)
                # build log file and save
                log_file_path = os.path.join(tmp_dir, 'log.txt')
                with open(os.path.join(tmp_dir, 'ice.log'), 'r') as f:
                    err_output = f.read()
                build_compile_fail_log(log_file_path, seed, error_state, mutation_operator_label, ' '.join(check_cmd), err_output)
                file_list.append(log_file_path)
                # create error dir and save
                program_seed = seed.split('/')[-1] if seed.find('/') != -1 else seed
                fail_type = program_seed + '-' + error_state + opt
                save_test(lock, file_list, compiler_name=compiler, fail_type=fail_type)
    


def check_program_by_all_sanitizers_with_one_single_threaded(clang_compiler, program_file_path, tmp_dir,
                                                             proc_num=-1, seed=-1, lock=None, mutation_operator_label=''):
    

    for sanitizer in ['MSAN', 'ASAN', 'UBSAN']:
        if not check_program_by_sanitizer_with_single_threaded(clang_compiler, sanitizer, 
                                          program_file_path, tmp_dir, 
                                          proc_num, seed, lock, 
                                          mutation_operator_label):
            return False
    return True


def check_program_by_all_sanitizers(clang_compiler, program_file_path, tmp_dir, 
                                    proc_num=-1, seed=-1, lock=None, mutation_operator_label=''):
    for crash_compiler in COMPILER2REAL.keys():
        check_compiler_ICE(crash_compiler, program_file_path, tmp_dir, proc_num, seed, lock, mutation_operator_label)


    for sanitizer in ['MSAN', 'ASAN', 'UBSAN']:
        if not check_program_by_sanitizer(clang_compiler, sanitizer, 
                                          program_file_path, tmp_dir, 
                                          proc_num, seed, lock, 
                                          mutation_operator_label):
            return False
    return True


if __name__ == "__main__":
    for ice_compiler in COMPILER2REAL.keys():
        check_compiler_ICE(ice_compiler, ['./test/test.c'], './test/ice')

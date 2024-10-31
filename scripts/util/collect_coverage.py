
import os
import sys
import time
import subprocess
import multiprocessing
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from util.sys_util import *
from util.mutate_util import *

COMPILER_COVERAGE_DIR = '/home/compilers/llvm/llvm-cov-16.0.6'

thread_num = 20


line_coverage_set = set()
file_coverage_set = set()


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def gcov_files_in_chunk(cov_dir, chunk):
    subprocess.run(["gcov", " "] + chunk, cwd="./", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


def collect_coverage_info(compiler_coverage_dir, testing_dir, program_file_path, opt='', seed=None):
    os.chdir(testing_dir)

    # Generate target program
    gen_yarpgen_program = ['yarpgen', '--std=c']
    if seed is not None:
        gen_yarpgen_program += ['-s', str(seed)]
    run_command(gen_yarpgen_program)
    mutate_program(test_dir='.')

    compiler = os.path.join(compiler_coverage_dir, 'bin', 'clang')

    # Here are the remaining. gcda and. gcov files from previous
    cmd_find_gcda = ['find', compiler_coverage_dir, '-name', '*.gcda']
    cmd_find_gcov = ['find', '.', '-name', '*.gcov']
    _, gcda_file_paths, _, _, _ = run_command(cmd_find_gcda)
    _, gcov_file_paths, _, _, _ = run_command(cmd_find_gcov)
    gcda_file_paths = gcda_file_paths.decode().strip().split('\n')
    gcov_file_paths = gcov_file_paths.decode().strip().split('\n')
    cmd_rm_gcda = ['rm', '-f'] + gcda_file_paths
    cmd_rm_gcov = ['rm', '-f'] + gcov_file_paths
    run_command(cmd_rm_gcda)
    run_command(cmd_rm_gcov)

    # Compile and run the target program
    compile_target_program = [compiler] + program_file_path + ['-I/home/tools/csmith/include', opt]
    run_compiled_program = ['./a.out']
    ret_code, output, err_output, is_time_expired, elapsed_time = run_command(compile_target_program, time_out=30)
    if ret_code != 0 or is_time_expired:
        print('compile error')
        os.chdir('../..')
        return
    ret_code, output, err_output, is_time_expired, elapsed_time = run_command(run_compiled_program, time_out=30)
    if ret_code != 0 or is_time_expired:
        print('run error')
        os.chdir('../..')
        return

    # Find the current. gcda file and generate a. gcov file using gcov
    _, gcda_file_paths, _, _, _ = run_command(cmd_find_gcda)
    gcda_file_paths = gcda_file_paths.decode().strip().split('\n')
    if thread_num == 1:
        for gcda_file_path in gcda_file_paths:
            gcda_file_path = gcda_file_path
            if os.path.exists(gcda_file_path):
                run_command(['gcov', gcda_file_path])
    else:
        # Multi threaded computation
        # Running in three threads
        chunk_size = int(len(gcda_file_paths) / thread_num) + 1
        processes = []
        # Execute the gcov command on the gcda file to generate a gcov file containing code coverage information
        for chunk in chunks(gcda_file_paths, chunk_size):
            p = multiprocessing.Process(target=gcov_files_in_chunk, args=(compiler_coverage_dir, chunk))
            processes.append(p)
            p.start()
       
        for p in processes:
            p.join()

    _, gcov_file_paths, _, _, _ = run_command(cmd_find_gcov)
    gcov_file_paths = gcov_file_paths.decode().strip().split('\n')
    for gcov_file_path in gcov_file_paths:
        gcov_file_path = gcov_file_path.strip()
        file_coverage_set.add(gcov_file_path)

        if not os.path.exists(gcov_file_path):
            continue
        
        with open(gcov_file_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if line == '------------------\n':
                    continue
                line_list = line.strip().split(':')

                if len(line_list) < 2:
                    continue

                cov_cnt = line_list[0].strip()
                line_num = line_list[1].strip()

                if cov_cnt != '-' and cov_cnt != '#####':
                    line_coverage_set.add(gcov_file_path + ':' + line_num)

    
    cmd_rm_gcda = ['rm', '-f'] + gcda_file_paths
    cmd_rm_gcov = ['rm', '-f'] + gcov_file_paths
    run_command(cmd_rm_gcda)
    run_command(cmd_rm_gcov)

    os.chdir('../..')


if __name__ == '__main__':
    opts = ['-O0', '-O1', '-O2', '-O3', '-Os']

    program_file_path = [
        'init.h',
        'func.c',
        'driver.c'
    ]

    seeds_file = '/seeds/seeds_1t_0.txt'
    with open(seeds_file, 'r') as f:
        seeds = f.readlines()
        seeds = [int(seed.strip()) for seed in seeds][:1000]

    start_time = time.time()
    for i in range(1000):
        if i != 0:
            with open('./test/2-coverage_summary.txt', 'a+') as f:
                f.write('=====================\n')
                f.write('Number of iterations:' + str(i) + '\n')
                f.write('File coverage:' + str(len(file_coverage_set)) + '\n')
                f.write('Line coverage:' + str(len(line_coverage_set)) + '\n')
                f.write('Time consuming:' + str(time.time() - start_time) + '\n')
        
        if i % 100 == 99:
            with open('./test/2-line_coverage.txt', 'w') as f:
                for line in line_coverage_set:
                    f.write(line + '\n')
            with open('./test/2-file_coverage.txt', 'w') as f:
                for file in file_coverage_set:
                    f.write(file + '\n')

        for opt in opts:
            collect_coverage_info(COMPILER_COVERAGE_DIR, './test/coverage', program_file_path, opt=opt, seed=seeds[i])
            end_time = time.time()
            print(str(i) + 'th', 'time: ', end_time - start_time)
        print()

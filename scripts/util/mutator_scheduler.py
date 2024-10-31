#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import math
import numpy as np
import networkx as nx
import gmatch4py as gm
import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from util.mutate.mutate_config import *
import common
from common import run_cmd
from util.sys_util import *
from util.config import *
from util.tools import *

timeout = 180                   # 180s
compiler_mem_limit = 10000000   # 10 Gb


def read_cfg(cfgpath):
    # print('----begin read cfg file-----')
    fcfg = open(cfgpath)
    line = fcfg.readline()
    function = [[]]
    functionblock = []
    funflag = False
    while line:
        if line.startswith(';; Function func_') or line.startswith(
                ';; Function main'):
            if len(functionblock) != 0:
                function.append(functionblock)
                functionblock = []
            funflag = True
        elif 'func_' in line or 'main (' in line:
            funflag = False
        if funflag:
            functionblock.append(line)
        line = fcfg.readline()
    if len(functionblock) != 0:
        function.append(functionblock)
    # print('----end read cfg file-----')
    # print(str(function))
    # construct graph
    graph = nx.DiGraph()
    nodesetnum = set()
    for eachblock in function:
        eachbolcknum = []
        for eachline in eachblock:
            eachlinenodes = []
            if 'succs' in eachline:
                eachlinesplit = eachline.split(' ')
                for eachsplit in eachlinesplit:
                    if eachsplit.strip().isdigit():
                        eachlinenodes.append(eachsplit)
                        eachbolcknum.append(eachsplit)
                nodefirstnum = int(eachlinenodes[0]) + int(len(nodesetnum))
                for eachindex in eachlinenodes[1:]:
                    nodenum = int(len(nodesetnum)) + int(eachindex)
                    graph.add_edge(str(nodefirstnum), str(nodenum))
        for eachbolcknumkey in eachbolcknum:
            nodesetnum.add(eachbolcknumkey)
    return graph


def read_file(filepath):
    with open(filepath, 'r') as f:
        code = f.readlines()
    return code


def calc_jaccard_similarity(code1, code2):
    code1 = set(code1)
    code2 = set(code2)
    # len(code1 | code2) - len(code1 & code2) = len(set(code1) ^ set(code2))
    return len(code1 ^ code2) / len(code1 | code2)


def codedistance1(code1, code2):
    distance = 0.0
    chaji = list(set(code1) ^ set(code2))
    bingji = list(set(code1).union(set(code2)))
    distance = float(len(chaji) / len(bingji))
    return distance


total_cfg = []
total_code = []
mutate_label2rate_score = {}
last_avg_score = 0
def calculate(program_file_path, mutate_label2num, ub_caused_mutate_label2num, 
              mutate_label, is_free, compiler='/home/jwzeng/compilers/gcc/gcc-13.1.0/bin/gcc', proc_num=-1):
    generate_cfg = [compiler, '-c', '-fdump-tree-cfg-lineno', '-I' + CSMITH_INCLUDE_DIR] + program_file_path
    ret_code, output, err_output, is_time_expired, elapsed_time = \
        run_command(generate_cfg, timeout, proc_num, compiler_mem_limit)
    if ret_code == 0:
        cfg_path = program_file_path[0] + '.015t.cfg'
        new_cfg = read_cfg(cfg_path)
        new_code = read_file(program_file_path[0])
        # print(str(cfg_graph))
        
        sub_cfg_similarity = []
        sub_code_similarity = []

        ged = gm.GraphEditDistance(1, 1, 1, 1)
        ged_compare_res = ged.compare([new_cfg] + total_cfg, [0])
        cfg_similarities = ged.similarity(ged_compare_res)

        for i in range(len(total_cfg)):
            cfg_similarity = cfg_similarities[0][i + 1]
            code_similarity = calc_jaccard_similarity(new_code, total_code[i])

            sub_cfg_similarity.append(cfg_similarity)
            sub_code_similarity.append(code_similarity)

            # print('cfg_similarity:', cfg_similarity)
            # print('code_similarity:', code_similarity)
            # print('-----')
        sub_score = [sub_cfg_similarity[i] + sub_code_similarity[i] for i in range(len(sub_cfg_similarity))]
        avg_of_sub_score = free_score = 0
        if len(sub_score) != 0:
            avg_of_sub_score = sum(sub_score) / len(sub_score)
            if mutate_label in ub_caused_mutate_label2num:
                free_score = float((mutate_label2num[mutate_label] - ub_caused_mutate_label2num[mutate_label]) / mutate_label2num[mutate_label])
            else:
                free_score = 1.0
            # new_rate_score = avg_of_sub_score / mutate_label2num[mutate_label]
            print('sub_score:', avg_of_sub_score)
            print('free_score:', free_score)
            new_rate_score = avg_of_sub_score * free_score
            print('new_rate_score:', new_rate_score)
            print('------------------')

            mutate_label2rate_score[mutate_label] = new_rate_score

        total_cfg.append(new_cfg)
        total_code.append(new_code)

        # if not is_free:
        #     total_cfg.clear()
        #     total_code.clear()
        
        return mutate_label2rate_score


def log(name, msg):
    current_time = datetime.datetime.now()
    formatted_time = current_time.strftime("%y%m%d-%H_%M_%S")
    print('>>', formatted_time, name + ':', msg)


class MutatorScheduler:
    opts = ['insert-for', 
            'insert-if', 
            'insert-while', 
            'insert-assignment', 
            'insert-doWhile', 
            'insert-switch', 
            'insert-return',
            'prune-if', 
            'prune-for', 
            'prune-assignment', 
            'prune-compound', 
            'prune-return', 
            'replace-assignment']

    def __init__(self, total_code=[], total_cfg=[]):
        self.total_code = total_code
        self.total_cfg = total_cfg

        self.total_cnt = 0                 
        self.similarity_sum = 0            
        self.mutator2cnt_and_reward = {}    # mutator : [mutator_cnt, mutator_reward_sum]
        for opt in MutatorScheduler.opts:
            self.mutator2cnt_and_reward[opt] = [0, 0]

    def add_code_and_cfg(self, program_file_path, proc_num=-1):
        log('add_code_and_cfg', 'GCC compile for generating cfg file. Begin---')
        generate_cfg = [CFG_COMPILER, '-c', '-w', '-fdump-tree-cfg-lineno', 
                        '-I' + CSMITH_INCLUDE_DIR] + program_file_path
        ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_command(generate_cfg, timeout, proc_num, compiler_mem_limit)
        log('add_code_and_cfg', 'GCC compile for generating cfg file. End with ret_code ' + str(ret_code))
        
        if ret_code == 0:
            log('add_code_and_cfg', 'Read code and cfg. Begin---')

            new_code = read_file(program_file_path[0])
            new_cfg = read_cfg(cfgpath=program_file_path[0]+'.015t.cfg')

            log('add_code_and_cfg', 'Read code and cfg. End---')

            self.total_code.append(new_code)
            self.total_cfg.append(new_cfg)
        else:
            with open('mutator_scheduler_error.log', 'a+') as f:
                f.write('====== mutator scheduler error: =======\n')
                f.write('>> is_time_expired : ' + str(is_time_expired) + '\n')
                f.write('>> err_output      : ' + err_output.decode() + '\n')
                f.write('=======================================\n\n')

    def clear_code_and_cfg(self):
        self.total_code.clear()
        self.total_cfg.clear()

    def update_mutator2cnt_and_reward(self, mutate_label, reward):
        if self.mutator2cnt_and_reward[mutate_label] is None:
            self.mutator2cnt_and_reward[mutate_label] = [1, reward]
        else:
            self.mutator2cnt_and_reward[mutate_label][0] += 1
            self.mutator2cnt_and_reward[mutate_label][1] += reward

    def update_similarity_sum(self, sub_avg_of_similarity):
        self.similarity_sum += sub_avg_of_similarity 

    def get_mutator(self):
        max = -1
        selected_mutator = ""
        for mutator, cnt_and_reward in self.mutator2cnt_and_reward.items():
            t = self.total_cnt             
            tj = cnt_and_reward[0]          
            xji_sum = cnt_and_reward[1]    
            # UCB-1
            if tj != 0 and t > 1:
                res = float(xji_sum / tj) + math.sqrt((2 * np.log(t - 1)) / tj)
            else:
                res = sys.maxsize
            if res > max:
                max = res
                selected_mutator = mutator
        return selected_mutator

    def calc_reward_1(self, mutate_label, is_free, compiler='/home/jwzeng/compilers/gcc/gcc-13.1.0/bin/gcc', proc_num=-1):
        generate_cfg = [compiler, '-c', '-w', '-fdump-tree-cfg-lineno', 
                        '-I' + CSMITH_INCLUDE_DIR] + program_file_path
        ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_command(generate_cfg, timeout, proc_num, compiler_mem_limit)
        if ret_code == 0:
            cfg_path = program_file_path[0] + '.015t.cfg'
            new_cfg = read_cfg(cfg_path)
            new_code = read_file(program_file_path[0])
            cfg_similarity_list = []
            code_similarity_list = []
            ged = gm.GraphEditDistance(1, 1, 1, 1)
            ged_compare_res = ged.compare([new_cfg] + self.total_cfg, [0])
            cfg_similarities = ged.similarity(ged_compare_res)
            for i in range(len(self.total_cfg)):
                cfg_similarity = cfg_similarities[0][i + 1]
                code_similarity = calc_jaccard_similarity(new_code, self.total_code[i])

                cfg_similarity_list.append(cfg_similarity)
                code_similarity_list.append(code_similarity)
            sub_score = [cfg_similarity_list[i] + code_similarity_list[i] for i in range(len(cfg_similarity_list))]
            sub_avg_of_similarity = sum(sub_score) / len(sub_score)
            

            if self.total_cnt != 0:
                avg_of_similarity = float(self.similarity_sum / self.total_cnt)
            else:
                avg_of_similarity = 0


            if sub_avg_of_similarity > avg_of_similarity and is_free:
                reward = 1
            else:
                reward = 0

            self.update_mutator2cnt_and_reward(mutate_label, reward)

            self.update_similarity_sum(sub_avg_of_similarity)
        else:
            reward = 0
            self.update_mutator2cnt_and_reward(mutate_label, 0)

            with open('mutator_scheduler_error.log', 'a+') as f:
                f.write('====== mutator scheduler error: =======\n')
                f.write('>> is_time_expired : ' + str(is_time_expired) + '\n')
                f.write('>> err_output      : ' + err_output.decode() + '\n')
                f.write('=======================================\n\n')
        self.total_cnt += 1

    def calc_reward_2(self, mutate_label, is_free, compiler='/home/jwzeng/compilers/gcc/gcc-13.1.0/bin/gcc', proc_num=-1):
        reward = 1 if is_free else 0
        generate_cfg = [compiler, '-c', '-w', '-fdump-tree-cfg-lineno', 
                        '-I' + CSMITH_INCLUDE_DIR] + program_file_path
        ret_code, output, err_output, is_time_expired, elapsed_time = \
            run_command(generate_cfg, timeout, proc_num, compiler_mem_limit)
        if ret_code == 0:
            cfg_path = program_file_path[0] + '.015t.cfg'
            new_cfg = read_cfg(cfg_path)
            new_code = read_file(program_file_path[0])
            cfg_similarity_list = []
            code_similarity_list = []
            ged = gm.GraphEditDistance(1, 1, 1, 1)
            ged_compare_res = ged.compare([new_cfg] + self.total_cfg, [0])
            cfg_similarities = ged.similarity(ged_compare_res)
            for i in range(len(self.total_cfg)):
                cfg_similarity = cfg_similarities[0][i + 1]
                code_similarity = calc_jaccard_similarity(new_code, self.total_code[i])

                cfg_similarity_list.append(cfg_similarity)
                code_similarity_list.append(code_similarity)
            sub_score = [cfg_similarity_list[i] + code_similarity_list[i] for i in range(len(cfg_similarity_list))]
            sub_avg_of_similarity = sum(sub_score) / len(sub_score)

            if self.total_cnt != 0:
                avg_of_similarity = float(self.similarity_sum / self.total_cnt)
            else:
                avg_of_similarity = 0

            if sub_avg_of_similarity > avg_of_similarity:
                reward += 1

            self.update_similarity_sum(sub_avg_of_similarity)
        else:
            with open('mutator_scheduler_error.log', 'a+') as f:
                f.write('====== mutator scheduler error: =======\n')
                f.write('>> is_time_expired : ' + str(is_time_expired) + '\n')
                f.write('>> err_output      : ' + err_output.decode() + '\n')
                f.write('=======================================\n\n')
        self.update_mutator2cnt_and_reward(mutate_label, reward)
        self.total_cnt += 1


if __name__ == '__main__':
    t = 101            # Total number of mutations
    tj = 6         # tj represents the total number of choices for the jth transformer/restriction option up to the t-th iteration
    xji_sum = 0     # xji refers to the reward for the jth enhancer/restriction option in the i-th iteration; This is the total sum of tj times
    # UCB-1
    res = float(xji_sum / tj) + math.sqrt((2 * np.log(t - 1)) / tj)
    print(res)

#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import signal
import subprocess


def exec_cmd(cmd):
    p = os.popen(cmd,"r")
    rs = []
    line = ""
    while True:
         line = p.readline()
         if not line:
              break
     #     print(line.strip())
         rs.append(line)
    return rs


def run_command(cmd, time_out=None, num=-1, memory_limit=None):
    """
    Run command and return tuple of return code, 
    stdout, stderr, is_time_expired, elapsed_time.
    If return code is 0, the command was successful.
    @param cmd: command to run
    @param time_out: timeout for command
    @param num: number of process
    @param memory_limit: memory limit for command
    @return: tuple of return code, stdout, stderr, is_time_expired, elapsed_time
    """
    is_time_expired = False
    shell = False
    if memory_limit is not None:
        shell = True
        new_cmd = "ulimit -v " + str(memory_limit) + " ; "
        new_cmd += " ".join(i for i in cmd)
        cmd = new_cmd
    start_time = os.times()
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, shell=shell) as process:
        try:
            log_msg_str = "Running " + str(cmd)
            if num != -1:
                log_msg_str += " in process " + str(num)
            if time_out is None:
                log_msg_str += " without timeout"
            else:
                log_msg_str += " with " + str(time_out) + " timeout"
            output, err_output = process.communicate(timeout=time_out)
            ret_code = process.poll()
        except subprocess.TimeoutExpired:
            # Sigterm is good enough here and compared to sigkill gives a chance to the processes
            # to clean up after themselves.
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            # once in a while stdout/stderr may not exist when the process is killed, so using try.
            try:
                output, err_output = process.communicate()
            except ValueError:
                output = b''
                err_output = b''

            is_time_expired = True
            ret_code = None
        except:
            # Something really bad is going on, so better to send sigkill
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait()
            raise
    end_time = os.times()
    elapsed_time = end_time.children_user - start_time.children_user + \
                   end_time.children_system - start_time.children_system
    return ret_code, output, err_output, is_time_expired, elapsed_time

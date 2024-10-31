
import os
import sys
import datetime
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import common

res_dir = 'result'

# save file_list in [compiler_name]/[fail_type]/[classification]/[test_name]
# for example:
# - icc/miscompare/S_123456
# - icc/miscompare/SIMP/S_123456
# - clang/build_fail/assert_XXXX/S_123456
# - gcc/miscompare/S_123456
# - gen_fail/S_20161230_22_30
# return dir name
def save_test(lock, file_list, compiler_name=None, fail_type=None, classification=None, test_name=None):
    dest = ".." + os.sep + res_dir + \
                  ((os.sep + compiler_name) if (compiler_name is not None) else "") + \
                  ((os.sep + fail_type) if (fail_type is not None) else os.sep + "script_problem") + \
                  ((os.sep + classification) if (classification is not None) else "") + \
                  ((os.sep + test_name) if (test_name is not None) else os.sep + "FAIL_" + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    try:
        lock.acquire()
        dest = os.path.abspath(dest)
        common.check_dir_and_create(dest)
        for f in file_list:
            common.check_and_copy(f, dest)
    except Exception as e:
        common.log_msg(logging.ERROR, "Problem when saving test in " + str(dest) + " directory")
        common.log_msg(logging.ERROR, "Exception type: " + str(type(e)))
        common.log_msg(logging.ERROR, "Exception args: " + str(e.args))
        common.log_msg(logging.ERROR, "Exception: " + str(e))

    finally:
        lock.release()

    return dest

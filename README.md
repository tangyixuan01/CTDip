# CTDip

Welcome to the homepage of CTDip, a compiler testing approach via diverse test program synthesis.

## Requirments

* YARPGen
We develop the tool of CTDip based on the testing framework of YARPGen. Building ``yarpgen`` is trivial. All you have to do is to use cmake:

```bash
mkdir build
cd build
cmake ..
make
```

* CSmith
We leverage CSmith to generate initial seed programs. 

* python 3
``` bash
pip install numpy networkx pycparser cython
```

* gmatch4py

``` bash
git clone https://github.com/Jacobe2169/GMatch4py.git
cd GMatch4py
(sudo) pip(3) install .
```

* compiler 

``` bash
apt install gcc-11 gcc-13 clang-14 clang-16
```

## Usage

To mutate seed programs, run the following command in the ``/util`` folder:
```bash
python mutate_util.py
```

Please use the following command to conduct compiler testing in the ``/scripts`` folder:

```bash
python run_onebyone.py -o /path-to-fuzzing-results --std c --programs-dir /path-to-test-programs --target "gcc clang" -j 10 --is-need-sanitizer
```

``-o``: output the fuzzing results

``--std c``: default option to test C program

``--programs-dir``: folder to be tested

``--target``: compilers under test

``-j``: number of processes

``--is-need-sanitizer``: whether to enable undefined behavior detection, default enabled

# S5 execution environment

All game processes explicitly use PYTHONHASHSEED=0, nice 10, OMP/OPENBLAS/MKL/VECLIB/RAYON/NUMEXPR thread limits 1. This pins Python set iteration across terminal equivalence and confirmation processes. No tracker source changes.

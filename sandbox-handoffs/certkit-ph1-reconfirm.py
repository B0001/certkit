import time
from certkit.checker import check
from certkit.operators import decode_operator, DENSE_LIMIT
from certkit.producer import certify_lambda_min, certify_lambda_min_matrixfree, tfim_hamiltonian

print(f"DENSE_LIMIT = {DENSE_LIMIT}\n")
for q in (4, 6, 8, 10, 12):
    enc = tfim_hamiltonian(q)
    n = decode_operator(enc).n
    for label, fn in (("temple_inertia", certify_lambda_min),
                       ("gershgorin_rayleigh", certify_lambda_min_matrixfree)):
        t0 = time.time()
        v = check(*fn(enc))
        dt = time.time() - t0
        if v.ok:
            print(f"q={q:2d} n={n:5d} {label:22s} width={v.width:.3e}  {dt:.2f}s")
        else:
            print(f"q={q:2d} n={n:5d} {label:22s} ABSTAIN: {v.reason[:60]}  {dt:.2f}s")
    print()

"""Quick ROCm/PyTorch sanity check."""
import torch

print(f"torch            : {torch.__version__}")
print(f"HIP (ROCm)       : {torch.version.hip}")
print(f"cuda.is_available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    dev = torch.device("cuda")
    print(f"device count     : {torch.cuda.device_count()}")
    print(f"device name      : {torch.cuda.get_device_name(0)}")

    # Small matmul on GPU, verified against CPU
    a = torch.randn(1024, 1024, device=dev)
    b = torch.randn(1024, 1024, device=dev)
    c = a @ b
    torch.cuda.synchronize()
    err = (c.cpu() - a.cpu() @ b.cpu()).abs().max().item()
    print(f"matmul max err   : {err:.2e}")
    print("GPU check PASSED" if err < 1e-2 else "GPU check FAILED (bad results)")
else:
    print("GPU check FAILED (no device visible)")

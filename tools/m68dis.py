import capstone,sys
d=open(sys.argv[1],'rb').read()
base=int(sys.argv[4],16) if len(sys.argv)>4 else 0
a=int(sys.argv[2],16); n=int(sys.argv[3],16)
md=capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000)
for ins in md.disasm(d[a-base:a-base+n],a):
    print(f"{ins.address:06x} {ins.bytes.hex():20} {ins.mnemonic} {ins.op_str}")

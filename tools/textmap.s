| Text remap for SUBCODE.BIN (sub CPU, GNU as, Motorola-style operands).
|
| A script file SPxx.BIN is loaded at $1A800; its text starts at $1E000
| (file offset 0x3800) and the bytecode names a string by its 16-bit offset
| from there. The Russian text is laid out anew, so each file carries a
| table (orig offset -> new offset) after its text, and the word at file
| offset 0x37FE (the bytecode area's FF padding) gives the table's offset
| from $1E000; 0xFFFF means no table. The four places that turn an offset
| into an address call these hooks instead (tools/textpatch.py).

        .equ    TEXT, 0x1E000
        .equ    TPTR, 0x1A800 + 0x37FE

        .text
        .globl  remap, hookS, hookA0, hookA1, hookB

| d0.w: offset as the bytecode has it -> d0.w: where it is now.
| Not in the table: unchanged. Binary search; table: N.w, N x (orig.w, new.w)
| sorted by orig. Other registers kept.
remap:
        movem.l %d1-%d6/%a1,-(%sp)
        move.w  (TPTR).l,%d1
        cmp.w   #0xFFFF,%d1
        beq.s   9f
        lea     (TEXT).l,%a1
        andi.l  #0xFFFF,%d1
        adda.l  %d1,%a1
        move.w  (%a1)+,%d3
        subq.w  #1,%d3                  | hi
        moveq   #0,%d2                  | lo
1:      cmp.w   %d2,%d3
        blt.s   9f
        move.w  %d2,%d4
        add.w   %d3,%d4
        lsr.w   #1,%d4                  | mid
        move.w  %d4,%d5
        lsl.w   #2,%d5
        move.w  (%a1,%d5.w),%d6
        cmp.w   %d6,%d0
        beq.s   2f
        bhi.s   3f
        move.w  %d4,%d3
        subq.w  #1,%d3
        bra.s   1b
3:      move.w  %d4,%d2
        addq.w  #1,%d2
        bra.s   1b
2:      move.w  2(%a1,%d5.w),%d0
9:      movem.l (%sp)+,%d1-%d6/%a1
        rts

| was: move.w ($97D0).l,($9746).l     - the dialogue line's start
hookS:
        move.l  %d0,-(%sp)
        move.w  (0x97D0).l,%d0
        bsr.w   remap
        move.w  %d0,(0x9746).l
        move.l  (%sp)+,%d0
        rts

| was: lea ($1E000).l,a0 / lea (a0,d7.w),a0
hookA0:
        move.l  %d0,-(%sp)
        move.w  %d7,%d0
        bsr.w   remap
        andi.l  #0xFFFF,%d0
        lea     (TEXT).l,%a0
        adda.l  %d0,%a0
        move.l  (%sp)+,%d0
        rts

| was: lea ($1E000).l,a1 / lea (a1,d7.w),a1
hookA1:
        move.l  %d0,-(%sp)
        move.w  %d7,%d0
        bsr.w   remap
        andi.l  #0xFFFF,%d0
        lea     (TEXT).l,%a1
        adda.l  %d0,%a1
        move.l  (%sp)+,%d0
        rts

| was: lea ($1E000).l,a0 / move.b (a0,d7.w),d0
hookB:
        move.w  %d7,%d0
        bsr     remap
        andi.l  #0xFFFF,%d0
        lea     (TEXT).l,%a0
        move.b  (%a0,%d0.l),%d0
        rts

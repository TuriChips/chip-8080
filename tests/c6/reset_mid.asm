; C6: reset in the middle of a run. The program sets SP, A, outputs A, enables interrupts (INTE = 1) and spins.
; The testbench resets it at one clock (+RESET_AT): after reset the pins must show the reset values (spec 5), INTE must be 0,
; and the first state must be T1 of a fetch from 0000, so the program runs again from the start and writes 5 a second time.
; Registers are not compared (spec 5: not reset), the program sets what it uses.
        .org 0
        LXI SP,0x4800
        MVI A,5
        OUT 1               ; 5
        EI
spin:   JMP spin

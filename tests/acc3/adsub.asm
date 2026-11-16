; Acceptance test 3, program 3 (spec section 9 item 3): the subroutine ADSUB from the Intel 8080/8085 Assembly Language
; Programming Manual, pp.6-4 and 6-5 (listing, both parameter lists), with our wrapper. This is the CALL/RET and stack case.
; From the manual (page images): ADSUB adds the first two bytes of the list at HL and stores the sum in the third.
;   PLIST = 6, 8, (result)     manual's figure on p.6-5 shows the result 0EH.
;   LIST2 = 10, 35, (result)   the manual says the sum is stored but prints no value: 45 = 2DH is OUR arithmetic.
; Ours: the listing in the manual is a fragment (the data sits in the instruction flow), so the data is placed after the code,
; SP is set, both calls are made, the two results are printed as hex ("0E" then "2D") and the program jumps to 0000h.
; Expected output: 0E2D
        .org 0
        JMP 0x0100
        .org 0x0100
        LXI SP,0xFFF0           ; ours
        LXI H,PLIST             ; manual: LOAD H AND L WITH ADDRESS OF THE PARAMETER LIST
        CALL ADSUB              ; manual: CALL THE SUBROUTINE
RET1:   LXI H,LIST2             ; manual: LOAD H AND L REGISTERS FOR ANOTHER CALL TO ADSUB
        CALL ADSUB
RET2:   LDA PLIST+2             ; ours from here: print the two results
        CALL PBYTE
        LDA LIST2+2
        CALL PBYTE
        MVI A,10
        OUT 0
        JMP 0x0000
; ---- from the manual, p.6-4 ----------------------------------------------------------------------
ADSUB:  MOV A,M                 ; GET FIRST PARAMETER
        INX H                   ; INCREMENT MEMORY ADDRESS
        MOV B,M                 ; GET SECOND PARAMETER
        ADD B                   ; ADD FIRST TO SECOND
        INX H                   ; INCREMENT MEMORY ADDRESS
        MOV M,A                 ; STORE RESULT AT THIRD PARAMETER STORE
        RET                     ; RETURN UNCONDITIONALLY
PLIST:  .byte 6, 8, 0           ; FIRST NUMBER, SECOND NUMBER, RESULT WILL BE STORED HERE
LIST2:  .byte 10, 35, 0
; ---- ours: print the byte in A as two hex digits through the BDOS port ---------------------------
PBYTE:  PUSH PSW
        RRC
        RRC
        RRC
        RRC
        CALL NIB
        POP PSW
NIB:    ANI 0x0F
        ADI 0x30
        CPI 0x3A
        JC OUTC
        ADI 7
OUTC:   OUT 0
        RET

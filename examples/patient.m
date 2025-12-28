; ============================================================================
; PATIENT.m - Patient Record Management
; A perfectly normal healthcare routine that definitely won't cause issues
;
; Your medical records, lovingly stored since 1966
; ============================================================================
;
PATIENT ; Patient Management Module
 ; Entry point - shouldn't be called directly
 W "Use specific entry points",!
 Q
 ;
; ============================================================================
; SEARCH - Find patient by name or ID
; Input: QUERY - search string
; Returns: Patient ID or "" if not found
; ============================================================================
SEARCH(QUERY)
 N ID,NAME,FOUND
 S FOUND=""
 ;
 ; First try exact ID match
 I QUERY?1.N S:$D(^PATIENT(QUERY)) FOUND=QUERY Q FOUND
 ;
 ; Search by name (case insensitive, naturally)
 S QUERY=$$UPPER(QUERY)
 S ID=""
 F  S ID=$O(^PATIENT(ID)) Q:ID=""  D  Q:FOUND'=""
 . S NAME=$G(^PATIENT(ID,"NAME"))
 . I $$UPPER(NAME)[QUERY S FOUND=ID
 Q FOUND
 ;
; ============================================================================
; GET - Retrieve patient record
; Input: ID - Patient identifier
; Returns: array by reference
; ============================================================================
GET(ID,DATA)
 K DATA
 I '$D(^PATIENT(ID)) Q 0
 ;
 M DATA=^PATIENT(ID)
 Q 1
 ;
; ============================================================================
; SAVE - Store patient record
; Input: ID - Patient ID, DATA - data array
; Returns: 1 on success, 0 on failure
; ============================================================================
SAVE(ID,DATA)
 N %
 ;
 ; Validate required fields
 I $G(DATA("NAME"))="" Q 0
 I $G(DATA("DOB"))="" Q 0
 ;
 ; Transaction for safety (your records matter, probably)
 TSTART
 M ^PATIENT(ID)=DATA
 S ^PATIENT(ID,"UPDATED")=$H
 S ^PATIENT(ID,"UPDATEDBY")=$J
 TCOMMIT
 ;
 Q 1
 ;
; ============================================================================
; DELETE - Remove patient record (HIPAA compliance sold separately)
; ============================================================================
DELETE(ID)
 I '$D(^PATIENT(ID)) Q 0
 ;
 TSTART
 K ^PATIENT(ID)
 TCOMMIT
 Q 1
 ;
; ============================================================================
; LIST - List all patients (pagination? what's that?)
; ============================================================================
LIST
 N ID,NAME,DOB,COUNT
 S COUNT=0
 ;
 W !,"Patient List",!
 W "============",!!
 ;
 S ID=""
 F  S ID=$O(^PATIENT(ID)) Q:ID=""  D
 . S NAME=$G(^PATIENT(ID,"NAME"),"Unknown")
 . S DOB=$G(^PATIENT(ID,"DOB"))
 . W ID,?10,NAME,?40,$$FMTDATE(DOB),!
 . S COUNT=COUNT+1
 ;
 W !,"Total: ",COUNT," patients",!
 Q
 ;
; ============================================================================
; ADDMED - Add medication to patient
; Input: ID - Patient ID, MED - Medication name, DOSE - Dosage
; ============================================================================
ADDMED(ID,MED,DOSE)
 I '$D(^PATIENT(ID)) Q 0
 I MED="" Q 0
 ;
 S ^PATIENT(ID,"MEDS",MED,"DOSE")=$G(DOSE)
 S ^PATIENT(ID,"MEDS",MED,"ADDED")=$H
 S ^PATIENT(ID,"MEDS",MED,"ADDEDBY")=$J
 Q 1
 ;
; ============================================================================
; LISTMEDS - List patient medications
; ============================================================================
LISTMEDS(ID)
 N MED,DOSE
 I '$D(^PATIENT(ID)) W "Patient not found",! Q
 ;
 W !,"Medications for: ",$G(^PATIENT(ID,"NAME")),!
 W "-----------------------------------",!
 ;
 S MED=""
 F  S MED=$O(^PATIENT(ID,"MEDS",MED)) Q:MED=""  D
 . S DOSE=$G(^PATIENT(ID,"MEDS",MED,"DOSE"),"Not specified")
 . W MED,?30,DOSE,!
 Q
 ;
; ============================================================================
; ALLERGIES - Manage patient allergies
; Because adverse drug events are no joke
; ============================================================================
ADDALRG(ID,ALLERGEN,REACTION)
 I '$D(^PATIENT(ID)) Q 0
 S ^PATIENT(ID,"ALLERGIES",ALLERGEN)=$G(REACTION,"Unknown reaction")
 Q 1
 ;
CHKALRG(ID,MED)
 ; Check if patient is allergic to medication
 ; Returns: 0=No, 1=Yes (probably should check this before prescribing)
 N ALLERGEN,FOUND
 S FOUND=0
 S ALLERGEN=""
 F  S ALLERGEN=$O(^PATIENT(ID,"ALLERGIES",ALLERGEN)) Q:ALLERGEN=""  D
 . I MED[ALLERGEN S FOUND=1
 . I ALLERGEN[MED S FOUND=1
 Q FOUND
 ;
; ============================================================================
; UTILITY FUNCTIONS
; The unglamorous but necessary bits
; ============================================================================
;
UPPER(STR)
 ; Convert string to uppercase
 Q $TR(STR,"abcdefghijklmnopqrstuvwxyz","ABCDEFGHIJKLMNOPQRSTUVWXYZ")
 ;
FMTDATE(H)
 ; Format $HOROLOG date for human consumption
 ; $H counts days since Dec 31, 1840 because why not
 N Y,D,M,DAYS
 I H="" Q ""
 S H=+H ; Get date portion only
 ;
 ; Approximate calculation (leap years are someone else's problem)
 S Y=H\365.25+1841
 S D=H#365.25
 ;
 ; Figure out month (close enough for government work)
 S M=D\30+1
 S D=D#30+1
 ;
 Q M_"/"_D_"/"_Y
 ;
TODAY()
 ; Return today's date in $H format
 Q +$H
 ;
; ============================================================================
; TEST - Self-test routine
; Because even healthcare software needs testing (theoretically)
; ============================================================================
TEST
 N ID,DATA,RESULT
 W !,"Running PATIENT tests...",!
 ;
 ; Test 1: Save and retrieve
 S ID=$$TEST1
 W "Test 1 (Save/Get): ",$S(ID:"PASS",1:"FAIL"),!
 ;
 ; Test 2: Medications
 S RESULT=$$TEST2(ID)
 W "Test 2 (Medications): ",$S(RESULT:"PASS",1:"FAIL"),!
 ;
 ; Test 3: Allergies
 S RESULT=$$TEST3(ID)
 W "Test 3 (Allergies): ",$S(RESULT:"PASS",1:"FAIL"),!
 ;
 ; Cleanup
 D DELETE(ID)
 W !,"Tests complete",!
 Q
 ;
TEST1()
 N DATA,ID,RETRIEVED
 S ID="TEST"_$J
 S DATA("NAME")="Test Patient"
 S DATA("DOB")=$$TODAY-10000
 I '$$SAVE(ID,.DATA) Q 0
 I '$$GET(ID,.RETRIEVED) Q 0
 I RETRIEVED("NAME")'=DATA("NAME") Q 0
 Q ID
 ;
TEST2(ID)
 I '$$ADDMED(ID,"Aspirin","81mg daily") Q 0
 I '$$ADDMED(ID,"Metformin","500mg twice daily") Q 0
 I '$D(^PATIENT(ID,"MEDS","Aspirin")) Q 0
 Q 1
 ;
TEST3(ID)
 I '$$ADDALRG(ID,"Penicillin","Anaphylaxis") Q 0
 I '$$CHKALRG(ID,"Penicillin") Q 0
 I $$CHKALRG(ID,"Aspirin") Q 0
 Q 1

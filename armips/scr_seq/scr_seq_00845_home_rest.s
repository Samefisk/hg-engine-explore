.nds
.thumb

.include "armips/include/scriptmacros.s"
.include "armips/include/vars.s"

// New Bark player house 1F, Mom's regular conversation. The original member
// is 0x490 bytes. Redirect only its menu setup at 0x275; keep the existing
// withdraw, deposit, savings, and exit branches at their original offsets.
.open "build/a012/2_845", 0
.org 0x275
    goto MomHomeMenu

.org 0x490
MomHomeMenu:
    npc_msg 20
    scrcmd_795 1, 1
    touchscreen_menu_hide
    menu_init 1, 1, 0, 1, VAR_SPECIAL_RESULT
    menu_item_add 29, 255, 0
    menu_item_add 30, 255, 1
    menu_item_add 39, 255, 4
    menu_item_add 31, 255, 2
    // Keep Quit last: B cancels to the final item in this menu.
    menu_item_add 32, 255, 3
    menu_exec
    switch VAR_SPECIAL_RESULT
    case 0, 0x2DF
    case 1, 0x335
    case 2, 0x398
    case 3, 0x3D1
    case 4, MomHomeRest
    goto 0x3D1

MomHomeRest:
    scrcmd_796
    touchscreen_menu_show
    closemsg
    callstd std_fade_heal_fade
    // The field service commits Mom as the healing point after party heal.
    setvar VAR_TEMP_x401F, 2
    npc_msg 40
    wait_button
    closemsg
    releaseall
    end
.close

// Select generated game assets once per launch. Reconnecting a pad cannot
// retroactively replace a font/layout the game already loaded into its heap.
#import <Foundation/Foundation.h>
#import <GameController/GameController.h>
#include "dm.h"

void dm_controller_icons_prepare(void) {
    const char *e = getenv("DM_CONTROLLER_ICONS");
    NSString *style = e && *e ? @(e) : @"auto";
    if ([style isEqualToString:@"auto"]) {
        GCController *pad = GCController.controllers.firstObject;
        GCExtendedGamepad *profile = pad.extendedGamepad;
        if ([profile isKindOfClass:GCDualSenseGamepad.class] || [profile isKindOfClass:GCDualShockGamepad.class]) style = @"playstation";
        else if ([profile isKindOfClass:GCXboxGamepad.class]) style = @"xbox";
        else style = @"original"; // unknown layouts must not be mislabeled as Xbox
    }
    if ([style isEqualToString:@"original"]) { unsetenv("DM_CONTROLLER_MODS_ROOT"); return; }
    if (![style isEqualToString:@"xbox"] && ![style isEqualToString:@"playstation"]) return;
    NSURL *root = [[NSBundle.mainBundle.resourceURL URLByAppendingPathComponent:@"ControllerIcons"] URLByAppendingPathComponent:style];
    if (![NSFileManager.defaultManager fileExistsAtPath:[[root URLByAppendingPathComponent:@"icons.json"] path]]) {
        LOG("controller icons: %s assets are not included for this game/build; original prompts kept", style.UTF8String); return;
    }
    setenv("DM_CONTROLLER_MODS_ROOT", root.path.UTF8String, 1);
    LOG("controller icons: %s, physical-position mapping; selected before game fonts are loaded", style.UTF8String);
}

// Live controls stay outside the virtual gamepad, including with a controller.
#import <UIKit/UIKit.h>
#include "nvn_tuning.h"
#include <stdlib.h>
#include <string.h>

static BOOL fixed_key(NSString *key) {
    for (const char **p = (const char *[]){"DM_ENV_FILE_KEYS", "DM_ENV_LAUNCH_KEYS", NULL}; *p; p++) {
        const char *e = getenv(*p); if (!e) continue;
        NSArray *keys = [@(e) componentsSeparatedByCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
        if ([keys containsObject:key]) return YES;
    }
    return NO;
}

@interface DmTuningVC : UITableViewController
@property (nonatomic, copy) void (^changed)(void);
@property (nonatomic, strong) NSTimer *timer;
@property (nonatomic, strong) UILabel *summary;
@end
@implementation DmTuningVC
- (void)viewDidLoad {
    [super viewDidLoad]; self.title = @"Graphics and performance";
    self.navigationItem.rightBarButtonItem = [[UIBarButtonItem alloc] initWithTitle:@"Resume" style:UIBarButtonItemStyleDone target:self action:@selector(resume)];
    self.summary = [UILabel new]; self.summary.numberOfLines = 0;
    self.summary.font = [UIFont monospacedSystemFontOfSize:12 weight:UIFontWeightRegular];
    self.summary.frame = CGRectMake(16, 0, 600, 115); self.tableView.tableHeaderView = self.summary;
    __weak DmTuningVC *weak = self;
    self.timer = [NSTimer scheduledTimerWithTimeInterval:1 repeats:YES block:^(NSTimer *timer) { (void)timer; [weak updateSummary]; }];
    [self updateSummary];
}
- (void)updateSummary { char text[768]; dm_tuning_describe(text, sizeof text); self.summary.text = @(text); }
- (void)resume { [self.timer invalidate]; self.timer = nil; [self dismissViewControllerAnimated:YES completion:nil]; }
- (void)viewDidDisappear:(BOOL)animated { [super viewDidDisappear:animated]; [self.timer invalidate]; self.timer = nil; }
- (NSArray<NSArray *> *)rows {
    dm_tuning_snapshot s = dm_tuning_read(); dm_tuning_config c = s.requested;
    NSMutableArray *rows = [NSMutableArray array];
    if (s.capabilities & DM_TUNE_SCALE) {
        [rows addObject:@[@"DM_AUTO_QUALITY", @"Automatic quality", @(c.automatic), @[@0,@1], @[@"Off",@"On"]]];
        [rows addObject:@[@"DM_FPS_TARGET", @"FPS target", @(c.target), @[@30,@60], @[@"30",@"60"]]];
        NSMutableArray *heights = [NSMutableArray array], *labels = [NSMutableArray array];
        for (NSNumber *number in @[@540,@576,@612,@648,@684,@720]) {
            int h = number.intValue; if (h < s.height / 2 || h > s.height) continue;
            [heights addObject:number]; [labels addObject:[NSString stringWithFormat:@"%dp internal", h]];
        }
        [rows addObject:@[@"DM_AUTO_MIN_HEIGHT", @"Minimum internal resolution", @(c.min_height), heights, labels]];
        NSMutableArray *scales = [NSMutableArray array], *names = [NSMutableArray array];
        for (int p = 50; p <= 100; p += 5) { [scales addObject:@(p / 100.0)]; [names addObject:[NSString stringWithFormat:@"%d%% · %d × %d", p, s.width * p / 100, s.height * p / 100]]; }
        [rows addObject:@[@"DM_RENDER_SCALE", @"Manual / starting render scale", @(c.scale / 100.0), scales, names]];
        [rows addObject:@[@"DM_RENDER_FIXED", @"Lock full scale at 100%", @(c.fixed), @[@0,@1], @[@"Game's dynamic resolution",@"Fixed full scale"]]];
        [rows addObject:@[@"DM_AUTO_TEXTURE", @"Automatic texture filtering", @(c.auto_texture), @[@0,@1], @[@"Off",@"Allowed at resolution floor"]]];
    }
    [rows addObject:@[@"DM_OUTPUT_HEIGHT", @"Display output", @(c.output), @[@720,@900,@1080,@0], @[@"720p",@"900p",@"1080p",@"Native display"]]];
    [rows addObject:@[@"DM_PRESENT_UPSCALE", @"Upscaling", @(c.upscale), @[@0,@1], @[@"Standard",@"MetalFX spatial"]]];
    [rows addObject:@[@"DM_TEXTURE_DETAIL", @"Texture filtering / mip detail", @(c.texture), @[@0,@1,@2], @[@"Original",@"Anisotropy ≤2×",@"Anisotropy 1× · mip floor 1"]]];
    if (s.capabilities & DM_TUNE_CLIP) {
        [rows addObject:@[@"DM_VIEW_DISTANCE", @"Camera visibility limit", @(c.far_clip), @[@0,@10000,@7500,@5000,@2500,@1000,@500], @[@"Original",@"10000",@"7500",@"5000",@"2500",@"1000",@"500"]]];
        [rows addObject:@[@"DM_AUTO_VIEW", @"Automatic visibility reduction", @(c.auto_clip), @[@0,@1], @[@"Off",@"Allowed at resolution floor"]]];
        [rows addObject:@[@"DM_AUTO_VIEW_FLOOR", @"Minimum camera visibility", @(c.clip_floor), @[@500,@1000,@2000,@5000,@10000], @[@"500",@"1000",@"2000",@"5000",@"10000"]]];
    }
    return rows;
}
- (NSInteger)numberOfSectionsInTableView:(UITableView *)tableView { (void)tableView; return 2; }
- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section { (void)tableView; return section ? 1 : self.rows.count; }
- (NSString *)tableView:(UITableView *)tableView titleForFooterInSection:(NSInteger)section {
    (void)tableView;
    return section ? @"Measures actual displayed frames in the current scene for 30 seconds. This is not a guarantee for other locations. Opening this menu does not pause the game." : @"Changes apply while playing and are saved for the next launch. Automatic quality respects the internal resolution floor; 1080p output alone does not mean native 1080p. Camera visibility clips distant geometry, not actor traversal or terrain LOD. Texture detail changes sampling, not allocated texture sizes. Pipeline and controller-icon settings require the next launch.";
}
- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)index {
    (void)tableView;
    UITableViewCell *cell = [[UITableViewCell alloc] initWithStyle:UITableViewCellStyleSubtitle reuseIdentifier:nil];
    if (index.section) { cell.textLabel.text = @"Measure current scene for 30 seconds"; cell.accessoryType = UITableViewCellAccessoryDisclosureIndicator; return cell; }
    NSArray *row = self.rows[index.row]; NSString *key = row[0]; NSNumber *current = row[2]; NSArray *values = row[3], *names = row[4];
    cell.textLabel.text = row[1]; BOOL locked = fixed_key(key);
    if (locked) cell.detailTextLabel.text = @"Fixed by env.txt / launch environment";
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem]; button.showsMenuAsPrimaryAction = YES;
    NSUInteger selected = [values indexOfObject:current];
    [button setTitle:selected < names.count ? names[selected] : current.stringValue forState:UIControlStateNormal];
    NSMutableArray *actions = [NSMutableArray array];
    __weak DmTuningVC *weak = self;
    for (NSUInteger i = 0; i < values.count; i++) {
        NSNumber *value = values[i]; UIAction *a = [UIAction actionWithTitle:names[i] image:nil identifier:nil handler:^(UIAction *action) {
            (void)action;
            if (!dm_tuning_set(key.UTF8String, value.doubleValue)) return;
            NSString *saved = [key isEqualToString:@"DM_PRESENT_UPSCALE"] ? (value.intValue ? @"metalfx" : @"off") : value.stringValue;
            [NSUserDefaults.standardUserDefaults setObject:saved forKey:[@"launcher." stringByAppendingString:key]];
            if (weak.changed) weak.changed(); [weak.tableView reloadData]; [weak updateSummary];
        }];
        a.state = [current isEqual:value] ? UIMenuElementStateOn : UIMenuElementStateOff;
        a.attributes = locked ? UIMenuElementAttributesDisabled : 0; [actions addObject:a];
    }
    button.menu = [UIMenu menuWithTitle:@"" children:actions]; [button sizeToFit]; cell.accessoryView = button;
    return cell;
}
- (void)tableView:(UITableView *)tableView didSelectRowAtIndexPath:(NSIndexPath *)index {
    [tableView deselectRowAtIndexPath:index animated:YES];
    if (index.section) { dm_tuning_measure(); [self resume]; }
}
@end
void dm_show_tuning(UIViewController *parent, void (^changed)(void)) {
    DmTuningVC *page = [[DmTuningVC alloc] initWithStyle:UITableViewStyleInsetGrouped]; page.changed = changed;
    UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:page];
    nav.modalPresentationStyle = UIModalPresentationPageSheet;
    [parent presentViewController:nav animated:YES completion:nil];
}

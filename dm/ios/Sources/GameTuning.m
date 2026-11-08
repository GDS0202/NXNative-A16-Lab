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

// The measurement runs on the actual presentation clock while the user plays.
// Keep a small non-modal readout on the game screen; the graphics sheet closes,
// so leaving the result only in the sheet made the command seem ineffective.
@interface DmBenchmarkHUD : UIView
@property (nonatomic, strong) UILabel *statusLabel;
@property (nonatomic, strong) NSTimer *ticker;
@property (nonatomic, assign) uint64_t changesAtStart;
+ (void)showOnView:(UIView *)container;
- (void)refresh;
- (void)hide;
@end
@implementation DmBenchmarkHUD
+ (void)showOnView:(UIView *)container {
    if (!container) return;
    for (UIView *child in [container.subviews copy])
        if ([child isKindOfClass:DmBenchmarkHUD.class]) [(DmBenchmarkHUD *)child hide];
    DmBenchmarkHUD *hud = [DmBenchmarkHUD new];
    hud.changesAtStart = dm_tuning_read().changes;
    hud.backgroundColor = [UIColor.blackColor colorWithAlphaComponent:0.84];
    hud.layer.cornerRadius = 12;
    hud.clipsToBounds = YES;
    hud.translatesAutoresizingMaskIntoConstraints = NO;

    UILabel *label = [UILabel new];
    label.font = [UIFont monospacedSystemFontOfSize:12 weight:UIFontWeightMedium];
    label.textColor = UIColor.whiteColor;
    label.numberOfLines = 0;
    label.translatesAutoresizingMaskIntoConstraints = NO;
    hud.statusLabel = label;
    [hud addSubview:label];

    UIButton *hide = [UIButton buttonWithType:UIButtonTypeSystem];
    [hide setTitle:@"Hide" forState:UIControlStateNormal];
    [hide setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    hide.titleLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightSemibold];
    hide.accessibilityLabel = @"Hide benchmark overlay";
    hide.translatesAutoresizingMaskIntoConstraints = NO;
    [hide addTarget:hud action:@selector(hide) forControlEvents:UIControlEventTouchUpInside];
    [hud addSubview:hide];

    [container addSubview:hud];
    [NSLayoutConstraint activateConstraints:@[
        [hud.centerXAnchor constraintEqualToAnchor:container.centerXAnchor],
        [hud.topAnchor constraintEqualToAnchor:container.safeAreaLayoutGuide.topAnchor constant:8],
        [hud.widthAnchor constraintEqualToConstant:MIN(350.0, MAX(240.0, container.bounds.size.width - 24.0))],
        [hud.heightAnchor constraintGreaterThanOrEqualToConstant:66],
        [label.leadingAnchor constraintEqualToAnchor:hud.leadingAnchor constant:12],
        [label.topAnchor constraintEqualToAnchor:hud.topAnchor constant:8],
        [label.bottomAnchor constraintEqualToAnchor:hud.bottomAnchor constant:-8],
        [label.trailingAnchor constraintEqualToAnchor:hide.leadingAnchor constant:-8],
        [hide.trailingAnchor constraintEqualToAnchor:hud.trailingAnchor constant:-10],
        [hide.widthAnchor constraintEqualToConstant:39],
        [hide.centerYAnchor constraintEqualToAnchor:hud.centerYAnchor]
    ]];
    [hud refresh];
    __weak DmBenchmarkHUD *weakHUD = hud;
    hud.ticker = [NSTimer scheduledTimerWithTimeInterval:0.5 repeats:YES block:^(NSTimer *timer) {
        DmBenchmarkHUD *strongHUD = weakHUD;
        if (!strongHUD) { [timer invalidate]; return; }
        [strongHUD refresh];
    }];
}
- (void)refresh {
    dm_tuning_snapshot s = dm_tuning_read();
    if (s.measuring) {
        double elapsed = s.measured_seconds > 30.0 ? 30.0 : s.measured_seconds;
        self.statusLabel.text = [NSString stringWithFormat:@"Measuring scene %.1f / 30 s\n%d frames · %.1f FPS live",
                                 elapsed, s.measured_frames, s.measured_fps];
    } else if (s.measured_complete) {
        unsigned long long changes = s.changes >= self.changesAtStart ?
            (unsigned long long)(s.changes - self.changesAtStart) : 0;
        self.statusLabel.text = [NSString stringWithFormat:@"30 s done: %.1f FPS · P95 %.1f ms\n%d frames · %llu automatic changes",
                                 s.measured_fps, s.measured_p95, s.measured_frames, changes];
        [self.ticker invalidate]; self.ticker = nil;
    } else {
        self.statusLabel.text = @"Measurement interrupted\nSetting changed or scene was suspended";
        [self.ticker invalidate]; self.ticker = nil;
    }
}
- (void)hide { [self.ticker invalidate]; self.ticker = nil; [self removeFromSuperview]; }
- (void)dealloc { [self.ticker invalidate]; }
@end

@interface DmTuningVC : UITableViewController
@property (nonatomic, copy) void (^changed)(void);
@property (nonatomic, strong) NSTimer *timer;
@property (nonatomic, strong) UILabel *summary;
@property (nonatomic, strong) NSSet<NSString *> *supported;
@end
@implementation DmTuningVC
- (void)viewDidLoad {
    [super viewDidLoad]; self.title = @"Graphics and performance";
    NSURL *settingsURL = [NSBundle.mainBundle.resourceURL URLByAppendingPathComponent:@"dm/launcher.json"];
    NSData *data = [NSData dataWithContentsOfURL:settingsURL];
    id decoded = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
    NSDictionary *settings = [decoded isKindOfClass:NSDictionary.class] ? decoded : nil;
    NSMutableSet *supported = [NSMutableSet set];
    for (NSDictionary *setting in settings[@"settings"]) if ([setting[@"env"] isKindOfClass:NSString.class]) [supported addObject:setting[@"env"]];
    self.supported = supported;
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
        if (!c.automatic) [rows addObject:@[@"DM_RENDER_FIXED", @"Force selected internal scale", @(c.fixed), @[@0,@1], @[@"Game's dynamic resolution",@"Fixed selected scale"]]];
        [rows addObject:@[@"DM_AUTO_TEXTURE", @"Automatic texture filtering", @(c.auto_texture), @[@0,@1], @[@"Off",@"Allowed at resolution floor"]]];
    }
    [rows addObject:@[@"DM_OUTPUT_HEIGHT", @"Display output", @(c.output), @[@720,@900,@1080,@0], @[@"720p",@"900p",@"1080p",@"Native display"]]];
    [rows addObject:@[@"DM_PRESENT_UPSCALE", @"Upscaling", @(c.upscale), @[@0,@1], @[@"Standard",@"MetalFX spatial"]]];
    [rows addObject:@[@"DM_TEXTURE_DETAIL", @"Scene texture filtering (preserves LOD)", @(c.texture), @[@0,@1,@2], @[@"Original",@"Eligible anisotropy 2×",@"Eligible anisotropy 1×"]]];
    if (s.capabilities & DM_TUNE_CLIP) {
        [rows addObject:@[@"DM_VIEW_DISTANCE", @"Camera visibility limit", @(c.far_clip), @[@0,@10000,@7500,@5000,@2500,@1000,@500], @[@"Original",@"10000",@"7500",@"5000",@"2500",@"1000",@"500"]]];
        [rows addObject:@[@"DM_AUTO_VIEW", @"Automatic visibility reduction", @(c.auto_clip), @[@0,@1], @[@"Off",@"Allowed at resolution floor"]]];
        [rows addObject:@[@"DM_AUTO_VIEW_FLOOR", @"Minimum camera visibility", @(c.clip_floor), @[@500,@1000,@2000,@5000,@10000], @[@"500",@"1000",@"2000",@"5000",@"10000"]]];
    }
    // The same capability list drives startup and live controls; a Vulkan/GL
    // title must not show an NVN-only sampler control that cannot affect it.
    return [rows filteredArrayUsingPredicate:[NSPredicate predicateWithBlock:^BOOL(id value, NSDictionary *bindings) {
        NSArray *row = value; (void)bindings; return [self.supported containsObject:row[0]];
    }]];
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
            const char *keep = getenv("DM_SAVED_CHOICES");
            if (!keep || strcmp(keep, "0")) [NSUserDefaults.standardUserDefaults setObject:saved forKey:[@"launcher." stringByAppendingString:key]];
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
    if (index.section) {
        if (!dm_tuning_active()) return;
        UIViewController *game = self.navigationController.presentingViewController ?: self.view.window.rootViewController;
        dm_tuning_measure();
        [DmBenchmarkHUD showOnView:game.view];
        [self resume];
    }
}
@end
void dm_show_tuning(UIViewController *parent, void (^changed)(void)) {
    DmTuningVC *page = [[DmTuningVC alloc] initWithStyle:UITableViewStyleInsetGrouped]; page.changed = changed;
    UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:page];
    nav.modalPresentationStyle = UIModalPresentationPageSheet;
    [parent presentViewController:nav animated:YES completion:nil];
}

#!/usr/bin/env python3
"""
web/patch_main.py - Dynamic patcher for web/main.js.

Locates the Appearance settings block and injects the Режим рабочего стола toggle
if not already present. Safe, idempotent, and resilient to upstream changes.
"""

import sys
import os
import re

def patch_main(file_path):
    if not os.path.isfile(file_path):
        print(f"[web-patch] file not found: {file_path}", file=sys.stderr)
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "Режим рабочего стола" in content or "ag_desktop_mode" in content:
        print("[web-patch] Режим рабочего стола toggle already present in main.js")
        return True

    # 1. State hook injection pattern in Appearance component:
    # Matches: var C=g!==3,D=g!==2,E=F=>G=>{F===t&&v(G)}; or legacy var B=f!==3,C=f!==2,D=E=>G=>{E===r&&u(G)};
    hook_pattern = re.compile(r'(var\s+[A-Za-z0-9_$]+=[A-Za-z0-9_$]+!==3,\s*[A-Za-z0-9_$]+=[A-Za-z0-9_$]+!==2,\s*[A-Za-z0-9_$]+=[A-Za-z0-9_$]+=>\s*[A-Za-z0-9_$]+=>\{.*?\};)')
    hook_match = hook_pattern.search(content)

    # 2. JSX Theme element injection: find Theme element in Appearance
    theme_idx = content.find('{label:"Theme"')
    theme_match = None
    react_id = "A"
    if theme_idx != -1:
        # Search backwards within a reasonable window (e.g. 100 chars) for createElement
        window_start = max(0, theme_idx - 100)
        window_end = min(len(content), theme_idx + 500)
        window_text = content[window_start:window_end]
        theme_pattern = re.compile(
            r'([A-Za-z0-9_$]+)\.createElement\(([A-Za-z0-9_$]+),\{label:"Theme",.*?onSelect:[A-Za-z0-9_$]+\}\)'
        )
        theme_match = theme_pattern.search(window_text)
        if theme_match:
            react_id = theme_match.group(1)

    if not hook_match or not theme_match:
        print(f"[web-patch] patterns not matched: hook={bool(hook_match)}, theme={bool(theme_match)}", file=sys.stderr)
        return False

    orig_hook = hook_match.group(1)
    injected_hook = (
        f"var [isDesktop,setIsDesktop]=(0,{react_id}.useState)(()=>{{"
        "try{if(window.Android&&typeof window.Android.isDesktopMode==='function')return window.Android.isDesktopMode();"
        "var s=localStorage.getItem('ag_desktop_mode');return s===null?!1:s==='true'}catch(_){return !1}});"
        f"var onDesktopToggle=(0,{react_id}.useCallback)(v=>{{"
        "setIsDesktop(v);try{localStorage.setItem('ag_desktop_mode',String(v));"
        "if(window.Android&&typeof window.Android.setDesktopMode==='function')window.Android.setDesktopMode(v)}catch(_){}},[]);"
        + orig_hook
    )

    # Detect switch and setting item components
    # Look for setting item component used with rightElement or contrast setting
    item_comp = "v3"
    switch_comp = "dX"
    re_idx = content.find('rightElement:')
    if re_idx != -1:
        re_window = content[max(0, re_idx - 150):min(len(content), re_idx + 150)]
        item_m = re.search(r'([A-Za-z0-9_$]+)\.createElement\(([A-Za-z0-9_$]+),\{label:[^,]+,description:[^,]+,rightElement:', re_window)
        if item_m:
            item_comp = item_m.group(2)
        sw_m = re.search(r'rightElement:[A-Za-z0-9_$]+\.createElement\(([A-Za-z0-9_$]+),\{checked:', re_window)
        if sw_m:
            switch_comp = sw_m.group(1)

    orig_theme = theme_match.group(0)
    injected_theme = (
        orig_theme
        + f',{react_id}.createElement({item_comp},{{label:"Режим рабочего стола",description:"Use desktop viewport and user agent for the workspace",'
        + f'rightElement:{react_id}.createElement({switch_comp},{{checked:isDesktop,onCheckedChange:onDesktopToggle}})}})'
    )

    content = content.replace(orig_hook, injected_hook, 1)
    content = content.replace(orig_theme, injected_theme, 1)

    # 3. Default Settings & Sound Alerts Patches
    extra_patches = [
        # Byc: artifactReviewMode = TURBO ("Всегда продолжать"), enableSounds = true
        ("artifactReviewPolicy:I.ArtifactReviewMode.ALWAYS,secureModeEnabled:!1,explainAndFixInCurrentConversation:!0,conversationHistoryEnabled:!0,knowledgeEnabled:!0,enableSoundsForSpecialEvents:!1",
         "artifactReviewPolicy:I.ArtifactReviewMode.TURBO,secureModeEnabled:!1,explainAndFixInCurrentConversation:!0,conversationHistoryEnabled:!0,knowledgeEnabled:!0,enableSoundsForSpecialEvents:!0"),
        # hEa defaultPreset linux and macos = unrestricted_unix ("Turbo mode")
        ("macos:{presets:[\"default_unix\",\"full_machine_unix\",\"unrestricted_unix\"],defaultPreset:\"default_unix\"},\nlinux:{presets:[\"default_unix\",\"full_machine_unix\",\"unrestricted_unix\"],defaultPreset:\"default_unix\"}",
         "macos:{presets:[\"default_unix\",\"full_machine_unix\",\"unrestricted_unix\"],defaultPreset:\"unrestricted_unix\"},\nlinux:{presets:[\"default_unix\",\"full_machine_unix\",\"unrestricted_unix\"],defaultPreset:\"unrestricted_unix\"}"),
        ("macos:{presets:[\"default_unix\",\"full_machine_unix\",\"unrestricted_unix\"],defaultPreset:\"full_machine_unix\"},\nlinux:{presets:[\"default_unix\",\"full_machine_unix\",\"unrestricted_unix\"],defaultPreset:\"full_machine_unix\"}",
         "macos:{presets:[\"default_unix\",\"full_machine_unix\",\"unrestricted_unix\"],defaultPreset:\"unrestricted_unix\"},\nlinux:{presets:[\"default_unix\",\"full_machine_unix\",\"unrestricted_unix\"],defaultPreset:\"unrestricted_unix\"}"),
        # nonWorkspaceFileAccessPolicy default = ALLOW (Security preset: unrestricted_unix)
        ("nonWorkspaceFileAccessPolicy:N===I.AgentSettingPolicy.UNSPECIFIED||N===void 0?I.AgentSettingPolicy.ASK:N",
         "nonWorkspaceFileAccessPolicy:N===I.AgentSettingPolicy.UNSPECIFIED||N===void 0?I.AgentSettingPolicy.ALLOW:N"),
        # uJa and vJa: Never disable or block any execution or permission options
        ("function uJa(a,b,c){return c===\"project\"&&a===I.CascadeCommandsAutoExecution.UNSPECIFIED?!0:b===1?a===I.CascadeCommandsAutoExecution.OFF:b===2?a!==I.CascadeCommandsAutoExecution.EAGER:!0}",
         "function uJa(a,b,c){return !0}"),
        ("function vJa(a,b,c){return c===\"project\"&&a===I.AgentSettingPolicy.UNSPECIFIED?!0:b===1?a===I.AgentSettingPolicy.DENY:b===2?a!==I.AgentSettingPolicy.ALLOW:!0}",
         "function vJa(a,b,c){return !0}"),
        # sMb: Qb and qb - do not clamp EAGER down
        ("var Qb=(0,A.useMemo)(()=>M!==1||zb!==I.AgentSettingPolicy.ALLOW&&zb!==I.AgentSettingPolicy.ASK?M===2&&zb===I.AgentSettingPolicy.ALLOW?I.AgentSettingPolicy.ASK:zb:I.AgentSettingPolicy.DENY,[zb,M]),qb=\n(0,A.useMemo)(()=>L!==1||Wa!==I.CascadeCommandsAutoExecution.EAGER&&Wa!==I.CascadeCommandsAutoExecution.PROCEED_IN_SANDBOX?L===2&&Wa===I.CascadeCommandsAutoExecution.EAGER?I.CascadeCommandsAutoExecution.PROCEED_IN_SANDBOX:Wa:I.CascadeCommandsAutoExecution.OFF,[Wa,L])",
         "var Qb=zb,qb=Wa"),
        # sMb cb callback: when unrestricted_unix selected, also trigger artifactReviewMode and permissionPreset turbo
        ("Bb!==\"custom\"&&(Bb=gEa[Bb])&&(Ob(Bb.sandboxMode),vb(Bb.terminal),Ga(Bb.fileAccess),r?r(Bb.sandboxMode,Bb.terminal,Bb.fileAccess):(e(Bb.sandboxMode),g(Bb.terminal),m?.(Bb.fileAccess)))",
         "Bb!==\"custom\"&&(Bb=gEa[Bb])&&(Ob(Bb.sandboxMode),vb(Bb.terminal),Ga(Bb.fileAccess),Bb.slug===\"unrestricted_unix\"&&(b?.(\"turbo\"),w?.(\"turbo\")),r?r(Bb.sandboxMode,Bb.terminal,Bb.fileAccess):(e(Bb.sandboxMode),g(Bb.terminal),m?.(Bb.fileAccess)))"),
        # uMb: Clicking 'Full access' card sets CASCADE_AUTO_EXECUTION_POLICY: EAGER, NON_WORKSPACE_FILE_ACCESS_POLICY: ALLOW, PERMISSION_PRESET: TURBO, ARTIFACT_REVIEW_MODE: TURBO
        ("ua=async()=>{var Ya=\nd,Ua=d;try{S(\"normal\"),Ua(await Ya(D.setPrefValues({[Ui.ENABLE_TERMINAL_SANDBOX]:!1,[Ui.SECURE_MODE_ENABLED]:!1})))}finally{Ya()}}",
         "ua=async()=>{var Ya=\nd,Ua=d;try{S(\"normal\"),Ua(await Ya(D.setPrefValues({[Ui.ENABLE_TERMINAL_SANDBOX]:!1,[Ui.SECURE_MODE_ENABLED]:!1,[Ui.CASCADE_AUTO_EXECUTION_POLICY]:I.CascadeCommandsAutoExecution.EAGER,[Ui.NON_WORKSPACE_FILE_ACCESS_POLICY]:I.AgentSettingPolicy.ALLOW,[Ui.PERMISSION_PRESET]:I.AgentPermissionPreset.TURBO,[Ui.ARTIFACT_REVIEW_MODE]:I.ArtifactReviewMode.TURBO})))}finally{Ya()}}"),
        # QKb: Selecting EAGER directly saves setting without Cider warning
        ("G=(0,A.useCallback)(H=>{var J=a===Ui.CASCADE_AUTO_EXECUTION_POLICY&&H===I.CascadeCommandsAutoExecution.EAGER;q===\"Cider\"&&J&&F(H)||E(H)},[a,q,F,E])",
         "G=(0,A.useCallback)(H=>{E(H)},[a,q,F,E])"),
        # Qzc: Default CASCADE_AUTO_EXECUTION_POLICY and PERMISSION_PRESET to EAGER and TURBO
        ("case Ui.CASCADE_AUTO_EXECUTION_POLICY:return a.rootProvider.getState().userConfig?.userSettings?.autoExecutionPolicy??\nI.CascadeCommandsAutoExecution.UNSPECIFIED??I.CascadeCommandsAutoExecution.PROCEED_IN_SANDBOX;case Ui.PERMISSION_PRESET:return a.rootProvider.getState().userConfig?.userSettings?.permissionPreset??I.AgentPermissionPreset.UNSPECIFIED??I.AgentPermissionPreset.UNSPECIFIED;",
         "case Ui.CASCADE_AUTO_EXECUTION_POLICY:{var _ap=a.rootProvider.getState().userConfig?.userSettings?.autoExecutionPolicy;return(_ap===void 0||_ap===I.CascadeCommandsAutoExecution.UNSPECIFIED)?I.CascadeCommandsAutoExecution.EAGER:_ap};case Ui.PERMISSION_PRESET:{var _pp=a.rootProvider.getState().userConfig?.userSettings?.permissionPreset;return(_pp===void 0||_pp===I.AgentPermissionPreset.UNSPECIFIED)?I.AgentPermissionPreset.TURBO:_pp};"),
        # Qzc: Default ARTIFACT_REVIEW_MODE to TURBO
        ("case Ui.ARTIFACT_REVIEW_MODE:return a.rootProvider.getState().userConfig?.userSettings?.artifactReviewMode??I.ArtifactReviewMode.UNSPECIFIED??I.ArtifactReviewMode.UNSPECIFIED;",
         "case Ui.ARTIFACT_REVIEW_MODE:{var _ar=a.rootProvider.getState().userConfig?.userSettings?.artifactReviewMode;return(_ar===void 0||_ar===I.ArtifactReviewMode.UNSPECIFIED)?I.ArtifactReviewMode.TURBO:_ar};"),
        # LX: Default cascade prompt config to EAGER and TURBO
        ("var LX=a=>{var b=kV(),c=VC(Ui.CASCADE_AUTO_EXECUTION_POLICY),e=ynb(b);",
         "var LX=a=>{var b=kV(),c=VC(Ui.CASCADE_AUTO_EXECUTION_POLICY)??I.CascadeCommandsAutoExecution.EAGER,e=ynb(b)??I.ArtifactReviewMode.TURBO;c=(c===I.CascadeCommandsAutoExecution.UNSPECIFIED||c===void 0)?I.CascadeCommandsAutoExecution.EAGER:c;e=(e===I.ArtifactReviewMode.UNSPECIFIED||e===void 0)?I.ArtifactReviewMode.TURBO:e;"),
        # CM.turbo: include artifactReviewMode and browserJsExecutionPolicy in turbo preset
        ("turbo:{label:\"Turbo\",description:\"Run all commands without restrictions.\",prefValues:{[Ui.ENABLE_TERMINAL_SANDBOX]:!1,[Ui.CASCADE_AUTO_EXECUTION_POLICY]:I.CascadeCommandsAutoExecution.EAGER,[Ui.NON_WORKSPACE_FILE_ACCESS_POLICY]:I.AgentSettingPolicy.ALLOW,[Ui.PERMISSION_PRESET]:I.AgentPermissionPreset.TURBO}}",
         "turbo:{label:\"Turbo\",description:\"Run all commands without restrictions.\",prefValues:{[Ui.ENABLE_TERMINAL_SANDBOX]:!1,[Ui.CASCADE_AUTO_EXECUTION_POLICY]:I.CascadeCommandsAutoExecution.EAGER,[Ui.NON_WORKSPACE_FILE_ACCESS_POLICY]:I.AgentSettingPolicy.ALLOW,[Ui.PERMISSION_PRESET]:I.AgentPermissionPreset.TURBO,[Ui.ARTIFACT_REVIEW_MODE]:I.ArtifactReviewMode.TURBO,[Ui.BROWSER_JS_EXECUTION_POLICY]:I.BrowserJsExecutionPolicy.TURBO}}"),
        # M9 sound check default = true
        ("a?.getEnableSoundsForSpecialEvents()??!1",
         "a?.getEnableSoundsForSpecialEvents()??!0"),
        # soundFiles: includes quotaExceeded sound
        ("soundFiles:{cascadeDone:\"/antigravityCascadeDone.mp3\",actionRequired:\"/antigravityActionRequired.mp3\"}",
         "soundFiles:{cascadeDone:\"/antigravityCascadeDone.mp3\",actionRequired:\"/antigravityActionRequired.mp3\",quotaExceeded:\"/antigravityQuotaExceeded.wav\"}"),
        # wVb quota trigger
        ("wVb=a=>{var b=a.notificationId,c=a.icon,",
         "wVb=a=>{try{window.__agPlaySound&&window.__agPlaySound(\"quota\")}catch(_){}var b=a.notificationId,c=a.icon,")
    ]

    for p_orig, p_repl in extra_patches:
        if p_orig in content:
            content = content.replace(p_orig, p_repl, 1)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("[web-patch] Successfully patched settings defaults, sounds, and desktop toggle into main.js")
    return True

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "main.js")
    if not patch_main(path):
        sys.exit(1)

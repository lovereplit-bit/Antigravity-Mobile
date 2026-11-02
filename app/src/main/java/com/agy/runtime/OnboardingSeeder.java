package com.agy.runtime;

import android.content.Context;
import android.util.Log;

import com.agy.util.AtomicFileWriter;

import java.io.File;
import java.io.InputStream;

/**
 * Materializes a fully-onboarded state before the core starts, so the Welcome
 * wizard is skipped. Idempotent and non-destructive: only writes when the
 * target is absent (or a zero-byte stub).
 */
public final class OnboardingSeeder {

    private static final String TAG = "OnboardingSeeder";

    private OnboardingSeeder() {
    }

    public static void seed(Context appContext, File appData, File projects) {
        try {
            if (!appData.exists() && !appData.mkdirs()) {
                Log.w(TAG, "cannot create " + appData);
                return;
            }
            seedStateFile(appContext, "jetski_state.pbtxt", new File(appData, "jetski_state.pbtxt"));
            seedStateFile(appContext, "antigravity_state.pbtxt",
                    new File(appData, "antigravity_state.pbtxt"));

            // Seed default agent rules (AGENTS.md) and settings (config.json) into ~/.gemini/config/
            File configDir = projects.getParentFile();
            if (configDir != null && (configDir.isDirectory() || configDir.mkdirs())) {
                seedStateFile(appContext, "AGENTS.md", new File(configDir, "AGENTS.md"));
                File configFile = new File(configDir, "config.json");
                seedStateFile(appContext, "config.json", configFile);
                ensureTurboDefaults(configFile);
            }

            // The project store resolves its projects here; without the
            // pseudo-project file it logs project_store_get_file_missing.
            if (!projects.exists() && !projects.mkdirs()) {
                Log.w(TAG, "cannot create " + projects);
                return;
            }
            File outside = new File(projects, "outside-of-project.json");
            if (!outside.isFile()) {
                AtomicFileWriter.writeText(outside, "{}\n");
            }
        } catch (Exception e) {
            Log.w(TAG, "onboarding seed failed (continuing): " + e.getMessage());
        }
    }

    private static void seedStateFile(Context appContext, String assetName, File target)
            throws Exception {
        if (target.isFile() && target.length() > 0) {
            Log.i(TAG, "state present; left untouched: " + target);
            return;
        }
        try (InputStream in = appContext.getAssets().open(
                RuntimePaths.SEED_ASSET + "/" + assetName)) {
            String content = com.agy.util.IoUtil.readAll(in, "UTF-8");
            AtomicFileWriter.writeText(target, content);
        }
        Log.i(TAG, "seeded onboarding state (was missing): " + target);
    }

    private static void ensureTurboDefaults(File configFile) {
        if (!configFile.isFile() || configFile.length() == 0) {
            return;
        }
        try (java.io.InputStream in = new java.io.FileInputStream(configFile)) {
            String text = com.agy.util.IoUtil.readAll(in, "UTF-8");
            boolean changed = false;
            if (text.contains("CASCADE_COMMANDS_AUTO_EXECUTION_OFF")) {
                text = text.replace("CASCADE_COMMANDS_AUTO_EXECUTION_OFF", "CASCADE_COMMANDS_AUTO_EXECUTION_EAGER");
                changed = true;
            }
            if (!text.contains("permissionPreset")) {
                text = text.replace("\"autoExecutionPolicy\": \"CASCADE_COMMANDS_AUTO_EXECUTION_EAGER\",",
                        "\"autoExecutionPolicy\": \"CASCADE_COMMANDS_AUTO_EXECUTION_EAGER\",\n    \"permissionPreset\": \"AGENT_PERMISSION_PRESET_TURBO\",");
                changed = true;
            }
            if (changed) {
                AtomicFileWriter.writeText(configFile, text);
                Log.i(TAG, "enforced turbo defaults in: " + configFile);
            }
        } catch (Exception e) {
            Log.w(TAG, "failed enforcing turbo defaults in config.json: " + e.getMessage());
        }
    }
}

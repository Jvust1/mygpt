package dev.mygpt.companionv2;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

import dev.mygpt.spike.StudySupervisorRuntime;

/**
 * Signature-permission-protected explicit Book study-signal receiver.
 *
 * No screen state, idle time, notes, source body, answer, or model prompt is
 * accepted here.
 */
public final class BookStudySignalReceiver extends BroadcastReceiver {
    public static final String ACTION =
            "dev.mygpt.companionv2.action.BOOK_STUDY_EVENT_V1";

    @Override
    public void onReceive(Context context, Intent intent) {
        boolean accepted = false;
        try {
            if (intent == null
                    || !ACTION.equals(intent.getAction())
                    || !isExplicitToThisPackage(context, intent)) {
                throw new IllegalArgumentException("invalid study signal target");
            }

            Bundle extras = intent.getExtras();
            if (extras == null) throw new IllegalArgumentException("missing extras");

            StudySupervisorRuntime runtime = StudySupervisorRuntime.shared();
            String kind = required(extras, "kind");

            if ("REVOKE".equals(kind)) {
                runtime.revokeSignedSession();
                accepted = true;
            } else {
                accepted = runtime.acceptSigned(
                        kind,
                        required(extras, "session_id"),
                        extras.getLong("sequence", 0L),
                        extras.getLong("epoch", 0L),
                        extras.getLong("expires_at_ms", 0L),
                        System.currentTimeMillis()
                ).accepted;
            }
        } catch (RuntimeException ignored) {
            accepted = false;
        }

        if (isOrderedBroadcast()) {
            setResultCode(accepted
                    ? Activity.RESULT_OK
                    : Activity.RESULT_CANCELED);
        }
    }

    private static boolean isExplicitToThisPackage(Context context, Intent intent) {
        String packageName = context.getPackageName();
        if (packageName.equals(intent.getPackage())) return true;
        return intent.getComponent() != null
                && packageName.equals(intent.getComponent().getPackageName());
    }

    private static String required(Bundle extras, String key) {
        String value = extras.getString(key);
        if (value == null) throw new IllegalArgumentException("missing " + key);
        return value;
    }
}

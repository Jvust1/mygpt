package dev.mygpt.companionv2;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

import dev.mygpt.spike.BookContextMailbox;
import dev.mygpt.spike.BookContextSnapshot;

/**
 * Signature-permission-protected Book -> MyGPT ephemeral context receiver.
 *
 * It stores no Book text on disk.
 */
public final class BookContextReceiver extends BroadcastReceiver {
    public static final String PERMISSION =
            "dev.mygpt.companionv2.permission.BOOK_CONTEXT";
    public static final String ACTION_CONTEXT =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_V1";
    public static final String ACTION_CLEAR =
            "dev.mygpt.companionv2.action.BOOK_CONTEXT_CLEAR_V1";

    @Override
    public void onReceive(Context context, Intent intent) {
        int result = 0;
        try {
            String action = intent == null ? null : intent.getAction();
            if (intent == null || !isExplicitToThisPackage(context, intent)) {
                throw new IllegalArgumentException("Book broadcast must target MyGPT explicitly");
            }
            Bundle extras = intent.getExtras();
            if (extras == null) throw new IllegalArgumentException("missing extras");

            if (ACTION_CONTEXT.equals(action)) {
                BookContextSnapshot snapshot = new BookContextSnapshot(
                        required(extras, "session_id"),
                        extras.getLong("sequence", 0L),
                        required(extras, "course_id"),
                        required(extras, "book_id"),
                        required(extras, "book_version"),
                        required(extras, "section_id"),
                        required(extras, "source_id"),
                        required(extras, "source_sha256"),
                        BookContextSnapshot.Mode.fromWire(required(extras, "mode")),
                        extras.getLong("captured_at_ms", 0L),
                        extras.getLong("expires_at_ms", 0L),
                        extras.getString("title", ""),
                        required(extras, "text")
                );
                BookContextMailbox.shared().accept(snapshot, System.currentTimeMillis());
                result = 1;
            } else if (ACTION_CLEAR.equals(action)) {
                boolean cleared = BookContextMailbox.shared().clear(
                        required(extras, "session_id"),
                        extras.getLong("sequence", 0L),
                        extras.getLong("occurred_at_ms", 0L),
                        System.currentTimeMillis()
                );
                result = cleared ? 1 : 0;
            } else {
                throw new IllegalArgumentException("unknown Book action");
            }
        } catch (RuntimeException ignored) {
            // Fail closed. Never log Book source text or extras.
            result = 0;
        }

        if (isOrderedBroadcast()) {
            setResultCode(result == 1
                    ? android.app.Activity.RESULT_OK
                    : android.app.Activity.RESULT_CANCELED);
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

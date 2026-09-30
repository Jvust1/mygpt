package dev.mygpt.bookbridge;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;

/**
 * Small Book-side client for the signature-protected MyGPT bridge.
 *
 * It never reads screen state, stores textbook bodies, or performs network I/O.
 */
public final class BookCompanionClient {
    public interface DeliveryCallback {
        void onResult(DeliveryResult result);
    }

    public static final class DeliveryResult {
        public final boolean accepted;
        public final int resultCode;
        public final String status;

        DeliveryResult(boolean accepted, int resultCode, String status) {
            this.accepted = accepted;
            this.resultCode = resultCode;
            this.status = status;
        }
    }

    private interface Committer {
        void finish(boolean accepted);
    }

    private final Context appContext;
    private final Handler main;

    public BookCompanionClient(Context context) {
        if (context == null) throw new IllegalArgumentException("context is required");
        this.appContext = context.getApplicationContext();
        this.main = new Handler(Looper.getMainLooper());
    }

    public void sendContext(
            BookCompanionSession session,
            BookContextPayload payload,
            DeliveryCallback callback
    ) {
        requireCallback(callback);
        if (session == null) throw new IllegalArgumentException("session is required");
        if (payload == null) throw new IllegalArgumentException("payload is required");
        payload.requireIdentity(session);

        final long sequence = session.reserveContextSequence();
        final long nowMs = System.currentTimeMillis();

        Intent intent = new Intent(BookCompanionContract.ACTION_CONTEXT)
                .setPackage(BookCompanionContract.TARGET_PACKAGE)
                .putExtra("session_id", session.sessionId)
                .putExtra("sequence", sequence)
                .putExtra("course_id", payload.courseId)
                .putExtra("book_id", payload.bookId)
                .putExtra("book_version", payload.bookVersion)
                .putExtra("section_id", payload.sectionId)
                .putExtra("source_id", payload.sourceId)
                .putExtra("source_sha256", payload.sourceSha256)
                .putExtra("mode", payload.mode.wireValue)
                .putExtra("captured_at_ms", nowMs)
                .putExtra("expires_at_ms", nowMs + payload.ttlMs)
                .putExtra("title", payload.title)
                .putExtra("text", payload.text);

        sendOrdered(
                intent,
                accepted -> session.finishContextSequence(sequence, accepted),
                callback
        );
    }

    public void clearContext(
            BookCompanionSession session,
            DeliveryCallback callback
    ) {
        requireCallback(callback);
        if (session == null) throw new IllegalArgumentException("session is required");

        final long sequence = session.reserveContextSequence();
        Intent intent = new Intent(BookCompanionContract.ACTION_CONTEXT_CLEAR)
                .setPackage(BookCompanionContract.TARGET_PACKAGE)
                .putExtra("session_id", session.sessionId)
                .putExtra("sequence", sequence)
                .putExtra("occurred_at_ms", System.currentTimeMillis());

        sendOrdered(
                intent,
                accepted -> session.finishContextSequence(sequence, accepted),
                callback
        );
    }

    public void startStudy(
            BookCompanionSession session,
            long ttlMs,
            DeliveryCallback callback
    ) {
        requireCallback(callback);
        requireTtl(ttlMs);
        if (session == null) throw new IllegalArgumentException("session is required");

        final long nowMs = System.currentTimeMillis();
        final BookCompanionSession.StudyReservation reservation =
                session.reserveStudyStart(nowMs);

        Intent intent = studyIntent(
                session,
                reservation.kind,
                reservation.sequence,
                reservation.epoch,
                nowMs + ttlMs
        );

        sendOrdered(
                intent,
                accepted -> session.finishStudy(reservation, accepted),
                callback
        );
    }

    public void sendStudyEvent(
            BookCompanionSession session,
            BookCompanionContract.StudyKind kind,
            long ttlMs,
            DeliveryCallback callback
    ) {
        requireCallback(callback);
        requireTtl(ttlMs);
        if (session == null) throw new IllegalArgumentException("session is required");

        final BookCompanionSession.StudyReservation reservation =
                session.reserveStudyEvent(kind);

        Intent intent = studyIntent(
                session,
                reservation.kind,
                reservation.sequence,
                reservation.epoch,
                System.currentTimeMillis() + ttlMs
        );

        sendOrdered(
                intent,
                accepted -> session.finishStudy(reservation, accepted),
                callback
        );
    }

    public void revokeStudy(
            BookCompanionSession session,
            DeliveryCallback callback
    ) {
        requireCallback(callback);
        if (session == null) throw new IllegalArgumentException("session is required");

        Intent intent = new Intent(BookCompanionContract.ACTION_STUDY_EVENT)
                .setPackage(BookCompanionContract.TARGET_PACKAGE)
                .putExtra("kind", BookCompanionContract.StudyKind.REVOKE.name());

        sendOrdered(
                intent,
                session::finishRevoke,
                callback
        );
    }

    private static Intent studyIntent(
            BookCompanionSession session,
            BookCompanionContract.StudyKind kind,
            long sequence,
            long epoch,
            long expiresAtMs
    ) {
        return new Intent(BookCompanionContract.ACTION_STUDY_EVENT)
                .setPackage(BookCompanionContract.TARGET_PACKAGE)
                .putExtra("kind", kind.name())
                .putExtra("session_id", session.sessionId)
                .putExtra("sequence", sequence)
                .putExtra("epoch", epoch)
                .putExtra("expires_at_ms", expiresAtMs);
    }

    private void sendOrdered(
            Intent intent,
            Committer committer,
            DeliveryCallback callback
    ) {
        try {
            appContext.sendOrderedBroadcast(
                    intent,
                    null,
                    new BroadcastReceiver() {
                        @Override
                        public void onReceive(Context context, Intent ignored) {
                            int code = getResultCode();
                            boolean accepted = code == Activity.RESULT_OK;
                            try {
                                committer.finish(accepted);
                            } catch (RuntimeException error) {
                                callback.onResult(new DeliveryResult(
                                        false,
                                        code,
                                        "LOCAL_STATE_ERROR_" + error.getClass().getSimpleName()
                                ));
                                return;
                            }
                            callback.onResult(new DeliveryResult(
                                    accepted,
                                    code,
                                    accepted ? "ACCEPTED" : "REJECTED"
                            ));
                        }
                    },
                    main,
                    Activity.RESULT_CANCELED,
                    null,
                    null
            );
        } catch (RuntimeException error) {
            try {
                committer.finish(false);
            } catch (RuntimeException ignored) {
            }
            main.post(() -> callback.onResult(new DeliveryResult(
                    false,
                    Activity.RESULT_CANCELED,
                    "SEND_FAILED_" + error.getClass().getSimpleName()
            )));
        }
    }

    private static void requireCallback(DeliveryCallback callback) {
        if (callback == null) throw new IllegalArgumentException("callback is required");
    }

    private static void requireTtl(long ttlMs) {
        if (ttlMs < 1L || ttlMs > 300000L) {
            throw new IllegalArgumentException("ttlMs must be in 1..300000");
        }
    }
}

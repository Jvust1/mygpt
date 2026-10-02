package dev.mygpt.spike;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/** Production callback owner with synthetic stop/status side effects, not AudioTrack. */
public final class VoiceOutputCompletionSmoke {
    public static void main(String[] args) throws Exception {
        VoiceOutputCompletion owner = new VoiceOutputCompletion();
        AtomicInteger stops = new AtomicInteger();
        AtomicReference<String> status = new AtomicReference<String>("old playing");
        VoiceOutputCompletion.Lease old = owner.beginUtterance();
        owner.invalidate(); // stop/toggle invalidates the first callback
        VoiceOutputCompletion.Lease fresh = owner.beginUtterance();
        status.set("new playing");
        boolean accepted = owner.onFailure(old, () -> { owner.invalidate(); stops.incrementAndGet(); status.set("old failure"); });
        require(!accepted && stops.get() == 0 && status.get().equals("new playing") && owner.isCurrent(fresh),
                "stale failure must not stop the newer output or replace its status");

        VoiceOutputCompletion.Lease newest = owner.beginUtterance();
        require(newest != fresh, "every utterance receives a new lease");
        require(!owner.onSuccess(fresh, () -> status.set("stale success")), "out-of-order success rejected");
        require(!owner.onFailure(fresh, () -> stops.incrementAndGet()), "out-of-order failure rejected");
        require(owner.onSuccess(newest, () -> status.set("completed")), "current success accepted");
        require(!owner.onFailure(newest, () -> stops.incrementAndGet()), "completed lease cannot finish twice");
        require(status.get().equals("completed"), "no stale success status change");

        VoiceOutputCompletion.Lease failing = owner.beginUtterance();
        require(owner.onFailure(failing, () -> { owner.invalidate(); stops.incrementAndGet(); status.set("current failure"); }), "current failure accepted");
        require(stops.get() == 1 && status.get().equals("current failure"), "one current stop effect");
        owner.invalidate(); owner.invalidate();
        require(!owner.onSuccess(failing, () -> status.set("obsolete")), "repeated cancel is idempotent");
        require(!owner.isCurrent(null), "null is not an issued lease");
        VoiceOutputCompletion another = new VoiceOutputCompletion();
        require(!owner.isCurrent(another.beginUtterance()), "another owner cannot supply a lease");

        VoiceOutputCompletion.Lease reentrant = owner.beginUtterance();
        AtomicReference<VoiceOutputCompletion.Lease> next = new AtomicReference<VoiceOutputCompletion.Lease>();
        owner.onSuccess(reentrant, () -> next.set(owner.beginUtterance()));
        require(owner.isCurrent(next.get()), "completion does not erase a reentrant newer lease");
        VoiceOutputCompletion.Lease throwing = owner.beginUtterance();
        try { owner.onFailure(throwing, () -> { throw new IllegalStateException("fixture"); }); }
        catch (IllegalStateException expected) { }
        require(!owner.isCurrent(throwing), "throwing callback consumes its lease");

        // Admission is atomic with its synchronous UI callback. Invalidation
        // cannot acknowledge while an already-admitted callback is still running.
        VoiceOutputCompletion concurrent = new VoiceOutputCompletion();
        VoiceOutputCompletion.Lease active = concurrent.beginUtterance();
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1), invalidated = new CountDownLatch(1);
        AtomicReference<Throwable> failure = new AtomicReference<Throwable>();
        Thread callback = new Thread(() -> {
            try {
                concurrent.onSuccess(active, () -> {
                    entered.countDown();
                    try { require(release.await(2, TimeUnit.SECONDS), "release callback"); }
                    catch (InterruptedException error) { throw new AssertionError(error); }
                });
            } catch (Throwable error) { failure.set(error); }
        });
        callback.start(); require(entered.await(2, TimeUnit.SECONDS), "callback entered");
        Thread stop = new Thread(() -> { concurrent.invalidate(); invalidated.countDown(); });
        stop.start(); require(!invalidated.await(50, TimeUnit.MILLISECONDS), "invalidate waits for admitted callback");
        release.countDown(); callback.join(2000); stop.join(2000);
        require(invalidated.getCount() == 0 && !callback.isAlive() && !stop.isAlive(), "callbacks drain without deadlock");
        require(failure.get() == null, "worker assertions must not be lost");

        VoiceOutputCompletion.Lease destroyed = owner.beginUtterance();
        owner.close(); owner.close(); owner.invalidate();
        require(!owner.onFailure(destroyed, () -> status.set("destroyed failure")), "destroy rejects late failure");
        require(!owner.onSuccess(destroyed, () -> status.set("destroyed success")), "destroy rejects late success");
        try { owner.beginUtterance(); throw new AssertionError("closed owner cannot restart"); }
        catch (IllegalStateException expected) { }
        System.out.println("VoiceOutputCompletionSmoke PASS: stale success/failure, repeated cancel, per-utterance ownership and destroy");
    }
    private static void require(boolean value, String label) { if (!value) throw new AssertionError(label); }
}

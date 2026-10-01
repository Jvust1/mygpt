package dev.mygpt.spike;

/**
 * Completion ownership for the Android TTS callbacks.
 *
 * Carries the already-adapted Pipecat generation/turn-invalidation pattern into
 * the native client. The token is an in-memory object, never an identity or
 * credential. It gates synchronous completion side effects, not AudioTrack/JNI.
 * Source family: pipecat-ai/pipecat @ 49dea682fb84bfc515d881d00dfeaaa9e9f1075f.
 * Copyright (c) 2024-2026, Daily. BSD-2-Clause; see third_party/pipecat/LICENSE.
 */
public final class VoiceOutputCompletion implements AutoCloseable {
    public static final class Lease { private Lease() {} }
    private Lease current;
    private boolean closed;

    public synchronized Lease beginUtterance() {
        if (closed) throw new IllegalStateException("voice completion owner is closed");
        current = new Lease();
        return current;
    }

    public synchronized boolean isCurrent(Lease lease) {
        return !closed && lease != null && lease == current;
    }

    public synchronized void invalidate() { current = null; }

    public boolean onSuccess(Lease lease, Runnable action) { return complete(lease, action); }
    public boolean onFailure(Lease lease, Runnable action) { return complete(lease, action); }

    private synchronized boolean complete(Lease lease, Runnable action) {
        if (action == null) throw new IllegalArgumentException("completion action is required");
        if (!isCurrent(lease)) return false;
        // Consume before invoking: a callback may invalidate, throw, or begin a
        // newer utterance. Never clear a new lease after returning from it.
        current = null;
        action.run();
        return true;
    }

    @Override public synchronized void close() { closed = true; current = null; }
}

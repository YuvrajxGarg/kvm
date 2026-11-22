package pxl.kvm.core

import org.bouncycastle.crypto.digests.Blake2bDigest
import org.bouncycastle.crypto.modes.ChaCha20Poly1305
import org.bouncycastle.crypto.params.AEADParameters
import org.bouncycastle.crypto.params.KeyParameter
import java.security.SecureRandom
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** The same cryptography as kvm/crypto.py on the computer, byte for byte. */
object Crypto {
    private val random = SecureRandom()

    fun randomBytes(n: Int): ByteArray = ByteArray(n).also { random.nextBytes(it) }

    /** BLAKE2b with Python hashlib's `person` (zero-padded to 16 bytes) and optional key. */
    fun blake2b(data: ByteArray, person: String, key: ByteArray? = null, size: Int = 32): ByteArray {
        val p = ByteArray(16)
        person.toByteArray(Charsets.US_ASCII).copyInto(p)
        val d = Blake2bDigest(key, size, null, p)
        d.update(data, 0, data.size)
        return ByteArray(size).also { d.doFinal(it, 0) }
    }

    fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray =
        Mac.getInstance("HmacSHA256").run {
            init(SecretKeySpec(key, "HmacSHA256"))
            doFinal(data)
        }

    /** who is "phone" or "desktop". */
    fun qrProof(secret: ByteArray, who: String, ident: String): ByteArray =
        hmacSha256(secret, "$who:$ident".toByteArray(Charsets.UTF_8))

    fun qrPairKey(secret: ByteArray): ByteArray = blake2b(secret, "kvm-qr-key")

    /** (dialer->listener, listener->dialer) keys for one connection. */
    fun sessionKeys(pairKey: ByteArray, dialerNonce: ByteArray, listenerNonce: ByteArray): Pair<ByteArray, ByteArray> {
        val salt = dialerNonce + listenerNonce
        return blake2b(salt, "kvm-d2l", pairKey) to blake2b(salt, "kvm-l2d", pairKey)
    }

    private fun nonce(n: Long): ByteArray {
        val b = ByteArray(12)
        for (i in 0 until 8) b[4 + i] = (n ushr (8 * (7 - i))).toByte()
        return b
    }

    /** ChaCha20-Poly1305 (IETF) with a counter nonce, one per direction. */
    class Sealer(private val key: ByteArray) {
        private var n = 0L
        @Synchronized
        fun seal(data: ByteArray): ByteArray {
            n++
            val c = ChaCha20Poly1305()
            c.init(true, AEADParameters(KeyParameter(key), 128, nonce(n)))
            val out = ByteArray(c.getOutputSize(data.size))
            val k = c.processBytes(data, 0, data.size, out, 0)
            c.doFinal(out, k)
            return out
        }
    }

    class Opener(private val key: ByteArray) {
        private var n = 0L
        fun open(blob: ByteArray): ByteArray {
            n++
            val c = ChaCha20Poly1305()
            c.init(false, AEADParameters(KeyParameter(key), 128, nonce(n)))
            val out = ByteArray(c.getOutputSize(blob.size))
            try {
                val k = c.processBytes(blob, 0, blob.size, out, 0)
                c.doFinal(out, k)
            } catch (e: Exception) {
                throw java.io.IOException("frame failed authentication")
            }
            return out
        }
    }
}

fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }

fun String.unhex(): ByteArray = chunked(2).map { it.toInt(16).toByte() }.toByteArray()

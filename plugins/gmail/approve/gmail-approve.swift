// Gmail for Claude (gmail-approve.swift): the lock on gmail-send's Google sign-in. ADR 2026-11-05-d38d84.
// Installed under that name because macOS starts the prompt with it: "Gmail for Claude is trying to …".
//
// The refresh token is stored only encrypted, to a Secure Enclave key whose every use needs the owner's Touch ID
// (.biometryCurrentSet: no password fallback, and enrolling a new finger invalidates it). macOS enforces this,
// so no process, gmail-send included, can read the token without a scan the owner approves.
//
//   Gmail for Claude seal <dir>             token on stdin -> <dir>/key.se + <dir>/token.sealed (no prompt)
//   Gmail for Claude open <dir> <reason>    Touch ID showing <reason>, then the token on stdout
//   Gmail for Claude test <reason>          one Touch ID prompt; nothing is unlocked
//
// Exit 0 done, 1 declined, timed out or failed, 2 Touch ID or the Secure Enclave not available,
// 3 nothing sealed yet (sign in again).
import CryptoKit
import Foundation
import LocalAuthentication

let info = Data("gmail-send refresh token v1".utf8)

func fail(_ code: Int32, _ msg: String) -> Never {
    FileHandle.standardError.write("gmail-approve: \(msg)\n".data(using: .utf8)!)
    exit(code)
}

func context(_ reason: String) -> LAContext {
    let ctx = LAContext()
    ctx.localizedReason = reason
    ctx.localizedFallbackTitle = ""  // no "Enter Password": a prompt that appears while typing can't take keystrokes
    ctx.localizedCancelTitle = "Cancel"
    var unavailable: NSError?
    guard !reason.isEmpty, ctx.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &unavailable) else {
        fail(2, unavailable?.localizedDescription ?? "no reason given")
    }
    return ctx
}

func writePrivate(_ data: Data, _ url: URL) throws {
    let tmp = url.appendingPathExtension("new")
    FileManager.default.createFile(atPath: tmp.path, contents: data, attributes: [.posixPermissions: 0o600])
    _ = try FileManager.default.replaceItemAt(url, withItemAt: tmp)
}

func symmetricKey(_ secret: SharedSecret) -> SymmetricKey {
    secret.hkdfDerivedSymmetricKey(using: SHA256.self, salt: Data(), sharedInfo: info, outputByteCount: 32)
}

let args = Array(CommandLine.arguments.dropFirst())
guard let mode = args.first else { fail(1, "usage: seal <dir> | open <dir> <reason> | test <reason>") }

switch mode {
case "seal" where args.count == 2:
    guard SecureEnclave.isAvailable else { fail(2, "Secure Enclave not available") }
    let dir = URL(fileURLWithPath: args[1])
    let token = FileHandle.standardInput.readDataToEndOfFile()
    guard !token.isEmpty else { fail(1, "no token on stdin") }
    var err: Unmanaged<CFError>?
    guard let access = SecAccessControlCreateWithFlags(nil, kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
                                                       [.privateKeyUsage, .biometryCurrentSet], &err) else {
        fail(2, "access control: \(String(describing: err?.takeRetainedValue()))")
    }
    do {
        let key = try SecureEnclave.P256.KeyAgreement.PrivateKey(accessControl: access)
        let ephemeral = P256.KeyAgreement.PrivateKey()
        let box = try AES.GCM.seal(token, using: symmetricKey(try ephemeral.sharedSecretFromKeyAgreement(with: key.publicKey)))
        try writePrivate(key.dataRepresentation, dir.appendingPathComponent("key.se"))
        try writePrivate(ephemeral.publicKey.x963Representation + box.combined!, dir.appendingPathComponent("token.sealed"))
    } catch {
        fail(1, "seal failed: \(error.localizedDescription)")
    }
case "open" where args.count == 3:
    let dir = URL(fileURLWithPath: args[1])
    guard let keyBlob = try? Data(contentsOf: dir.appendingPathComponent("key.se")),
          let sealed = try? Data(contentsOf: dir.appendingPathComponent("token.sealed")), sealed.count > 65 else {
        fail(3, "no sealed sign-in")
    }
    let ctx = context(args[2])
    do {
        let key = try SecureEnclave.P256.KeyAgreement.PrivateKey(dataRepresentation: keyBlob, authenticationContext: ctx)
        let ephemeral = try P256.KeyAgreement.PublicKey(x963Representation: sealed.prefix(65))
        let secret = try key.sharedSecretFromKeyAgreement(with: ephemeral)  // the Touch ID prompt happens here
        let token = try AES.GCM.open(AES.GCM.SealedBox(combined: sealed.dropFirst(65)), using: symmetricKey(secret))
        FileHandle.standardOutput.write(token)
    } catch let e as LAError where e.code == .biometryNotAvailable || e.code == .biometryNotEnrolled {
        fail(2, e.localizedDescription)
    } catch {
        fail(1, "not unlocked: \(error.localizedDescription)")
    }
case "test" where args.count == 2:
    let ctx = context(args[1])
    let done = DispatchSemaphore(value: 0)
    var approved = false
    ctx.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: args[1]) { ok, _ in
        approved = ok
        done.signal()
    }
    if done.wait(timeout: .now() + 120) == .timedOut {
        ctx.invalidate()
        exit(1)
    }
    exit(approved ? 0 : 1)
default:
    fail(1, "usage: seal <dir> | open <dir> <reason> | test <reason>")
}

// Synthetic wire data only. No Nintendo assets, keys, LibHac or network needed.
using System;
using System.Buffers.Binary;
using System.IO;
using System.Security.Cryptography;
static class Tests {
    const ulong App = 0x01007ef00011e000;
    static void Check(bool v) { if (!v) throw new Exception("CNMT check failed"); }
    static byte[] Make(byte type, int ext = 0) {
        if (ext == 0) ext = type == 0x81 ? 0x18 : 0x10;
        byte[] v = new byte[0x20 + ext + 0x38 + 32];
        BinaryPrimitives.WriteUInt64LittleEndian(v, App + (type == 0x80 ? 0ul : type == 0x81 ? 0x800ul : 0x1001ul));
        BinaryPrimitives.WriteUInt32LittleEndian(v.AsSpan(8), type == 0x81 ? 1114112u : 0u);
        v[0xc] = type; BinaryPrimitives.WriteUInt16LittleEndian(v.AsSpan(0xe), (ushort)ext);
        v[0x10] = 1; BinaryPrimitives.WriteUInt64LittleEndian(v.AsSpan(0x20), type == 0x80 ? App + 0x800 : App);
        v[0x20 + ext + 0x20] = 0xab; v[0x20 + ext + 0x31] = 0x40; v[0x20 + ext + 0x36] = 1;
        Seal(v); return v;
    }
    static void Seal(byte[] v) { SHA256.HashData(v.AsSpan(0, v.Length - 32)).CopyTo(v.AsSpan(v.Length - 32)); }
    static void Bad(byte[] v) {
        try { PackageMetadata.Parse(v); throw new Exception("invalid CNMT accepted"); }
        catch (PackageMetadataException) { }
    }
    static void Main() {
        foreach (byte kind in new byte[] {0x80, 0x81, 0x82}) {
            var p = PackageMetadata.Parse(Make(kind));
            Check(p.CnmtDigestVerified);
            Check(p.ApplicationId == App.ToString("X16")); Check(p.Contents.Count == 1);
            Check(p.Contents[0].Size == 0x4000); Check(p.Contents[0].Id.StartsWith("ab"));
            Check(p.Version == (kind == 0x81 ? 1114112u : 0u));
        }
        Check(PackageMetadata.Parse(Make(0x82, 0x18)).Type == "AddOnContent");
        var good = Make(0x81);
        for (int n = 0; n < good.Length; n++) Bad(good.AsSpan(0, n).ToArray());
        foreach (int offset in new[] { 0, 8, 0xc, 0xe, 0x10, 0x12, 0x20, 0x30, good.Length - 1 }) {
            var bad = (byte[])good.Clone(); bad[offset] ^= 0x80; Bad(bad);
        }
        var platform = Make(0x80); platform[0xd] = 1; Seal(platform); Bad(platform);
        var count = Make(0x80); count[0x11] = 0xff; Seal(count); Bad(count);
        var extra = Make(0x81); extra[0x2c] = 1; Seal(extra); Bad(extra);
        // A stale digest is never accepted by default or by a different pin.
        var repacked = Make(0x80); repacked[^1] ^= 1;
        Bad(repacked);
        string pin = Convert.ToHexString(SHA256.HashData(repacked)).ToLowerInvariant();
        var pins = PackageMetadata.DigestAllowlist(pin.ToUpperInvariant());
        Check(!PackageMetadata.Parse(repacked, pins).CnmtDigestVerified);
        Check(PackageMetadata.Parse(repacked, pins).ApplicationId == App.ToString("X16"));
        var changed = (byte[])repacked.Clone(); changed[8] ^= 1;
        try { PackageMetadata.Parse(changed, pins); throw new Exception("different metadata accepted"); }
        catch (PackageMetadataException) { }
        // A matching pin does not excuse bad bounds or missing associations.
        foreach (int offset in new[] { 0x10, 0x20 }) {
            var invalid = (byte[])repacked.Clone();
            if (offset == 0x20) BinaryPrimitives.WriteUInt64LittleEndian(invalid.AsSpan(offset), 0);
            else invalid[offset] = 0;
            string hash = Convert.ToHexString(SHA256.HashData(invalid)).ToLowerInvariant();
            try { PackageMetadata.Parse(invalid, PackageMetadata.DigestAllowlist(hash)); throw new Exception("malformed pinned metadata accepted"); }
            catch (PackageMetadataException) { }
        }
        foreach (string invalid in new[] { "abc", pin + ",", new string('z', 64), " " + pin }) {
            try { PackageMetadata.DigestAllowlist(invalid); throw new Exception("malformed allowlist accepted"); }
            catch (PackageMetadataException) { }
        }
        Check(PackageMetadata.DigestAllowlist(null).Count == 0);
        Console.WriteLine("CNMT identity, associations, versions, 48-bit sizes, digest, exact pins, bounds and truncation: PASS");
    }
}

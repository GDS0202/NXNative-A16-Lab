// Independent, bounded reader for the packaged CNMT wire format. No game or
// key data is retained. Identity comes from the integrity-checked meta NCA,
// never a package filename or a ticket (one cartridge can contain many titles).
using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;

sealed class PackageContent {
    public string Id { get; set; }
    public ulong Size { get; set; }
    public byte Type { get; set; }
    public byte IdOffset { get; set; }
}

sealed class PackageRecord {
    public string TitleId { get; set; }
    public string ApplicationId { get; set; }
    public string PatchId { get; set; }
    public uint Version { get; set; }
    public string Type { get; set; }
    public string MetadataSha256 { get; set; }
    public List<PackageContent> Contents { get; set; } = new();
}

static class PackageMetadata {
    public const int MaxBytes = 16 << 20;
    public static PackageRecord Parse(ReadOnlySpan<byte> data) {
        if (data.Length < 0x40 || data.Length > MaxBytes)
            throw new InvalidDataException("invalid CNMT length");
        ulong id = BinaryPrimitives.ReadUInt64LittleEndian(data);
        uint version = BinaryPrimitives.ReadUInt32LittleEndian(data[8..]);
        byte type = data[0xc];
        int ext = BinaryPrimitives.ReadUInt16LittleEndian(data[0xe..]);
        int count = BinaryPrimitives.ReadUInt16LittleEndian(data[0x10..]);
        int metas = BinaryPrimitives.ReadUInt16LittleEndian(data[0x12..]);
        int needExt = type switch { 0x80 => 0x10, 0x81 => 0x18, 0x82 => 0x10, _ => 0 };
        if (needExt == 0) throw new InvalidDataException("unsupported content meta type (only Application, Patch and AddOnContent are supported)");
        if (id == 0 || ext < needExt || count == 0 || count > 4096 || metas > 4096 || 0x20 + ext > data.Length - 32)
            throw new InvalidDataException("invalid CNMT header or content count");
        // Switch 2 content needs a different code/shader path; never mislabel it
        // as a supported Switch package just because the extension is familiar.
        if (data[0xd] != 0) throw new InvalidDataException("unsupported content platform");
        uint extra = type == 0x81 ? BinaryPrimitives.ReadUInt32LittleEndian(data[0x2c..]) : 0;
        long expected = 0x20L + ext + count * 0x38L + metas * 0x10L + extra + 32;
        if (expected != data.Length) throw new InvalidDataException("truncated or inconsistent CNMT tables");
        if (!CryptographicOperations.FixedTimeEquals(SHA256.HashData(data[..^32]), data[^32..]))
            throw new InvalidDataException("CNMT digest mismatch");
        ulong parent = BinaryPrimitives.ReadUInt64LittleEndian(data[0x20..]);
        if (parent == 0) throw new InvalidDataException("CNMT association is missing");
        var record = new PackageRecord {
            TitleId = id.ToString("X16"), ApplicationId = (type == 0x80 ? id : parent).ToString("X16"),
            PatchId = type == 0x80 ? parent.ToString("X16") : null,
            Version = version, Type = type switch { 0x80 => "Application", 0x81 => "Patch", _ => "AddOnContent" },
            MetadataSha256 = Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant()
        };
        var ids = new HashSet<string>(StringComparer.Ordinal);
        for (int i = 0; i < count; i++) {
            var entry = data.Slice(0x20 + ext + i * 0x38, 0x38);
            string contentId = Convert.ToHexString(entry.Slice(0x20, 16)).ToLowerInvariant();
            ulong size = 0; for (int j = 0; j < 6; j++) size |= (ulong)entry[0x30 + j] << (8 * j);
            if (!ids.Add(contentId) || size == 0 || entry[0x36] > 6)
                throw new InvalidDataException("invalid or duplicate CNMT content");
            record.Contents.Add(new PackageContent { Id = contentId, Size = size, Type = entry[0x36], IdOffset = entry[0x37] });
        }
        return record;
    }
}

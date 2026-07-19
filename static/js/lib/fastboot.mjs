/**
 * Shared types, error classes, and enums for the WebUSB device library.
 */
// ---- Error Types ----
class DeviceError extends Error {
    cause;
    constructor(message, cause) {
        super(message);
        this.name = "DeviceError";
        this.cause = cause;
    }
}
class TimeoutError extends DeviceError {
    timeoutMs;
    constructor(message, timeoutMs) {
        super(message);
        this.name = "TimeoutError";
        this.timeoutMs = timeoutMs;
    }
}
class ProtocolError extends DeviceError {
    /** For fastboot FAIL responses or bootloader-specific errors */
    bootloaderMessage;
    constructor(message, options) {
        super(message, options?.cause);
        this.name = "ProtocolError";
        this.bootloaderMessage = options?.bootloaderMessage;
    }
}
class UsbError extends DeviceError {
    constructor(message, cause) {
        super(message, cause);
        this.name = "UsbError";
    }
}
// ---- Enums ----
var DeviceMode;
(function (DeviceMode) {
    DeviceMode["ADB"] = "adb";
    DeviceMode["Fastboot"] = "fastboot";
    DeviceMode["Recovery"] = "recovery";
    DeviceMode["Bootloader"] = "bootloader";
})(DeviceMode || (DeviceMode = {}));
var LogLevel;
(function (LogLevel) {
    LogLevel[LogLevel["Silent"] = 0] = "Silent";
    LogLevel[LogLevel["Error"] = 1] = "Error";
    LogLevel[LogLevel["Debug"] = 2] = "Debug";
})(LogLevel || (LogLevel = {}));
// ---- Logger ----
let currentLogLevel = LogLevel.Silent;
function setLogLevel(level) {
    currentLogLevel = level;
}
function getLogLevel() {
    return currentLogLevel;
}
function log(...args) {
    if (currentLogLevel >= LogLevel.Debug) {
        console.log("[lib]", ...args);
    }
}
function logError(...args) {
    if (currentLogLevel >= LogLevel.Error) {
        console.error("[lib]", ...args);
    }
}

/**
 * USB filter constants and transport type definitions.
 */
/** ADB interface: vendor class 0xFF, subclass 0x42, protocol 0x01 */
const ADB_USB_FILTER = {
    classCode: 0xff,
    subclassCode: 0x42,
    protocolCode: 0x01,
};
/** Fastboot interface: vendor class 0xFF, subclass 0x42, protocol 0x03 */
const FASTBOOT_USB_FILTER = {
    classCode: 0xff,
    subclassCode: 0x42,
    protocolCode: 0x03,
};
/** Default timeout for USB operations (30 seconds) */
const DEFAULT_TIMEOUT_MS = 30_000;
/** Maximum USB bulk transfer size (16 MB) */
const MAX_TRANSFER_SIZE = 16 * 1024 * 1024;

/**
 * WebUSB transport layer.
 *
 * Handles device discovery, USB interface claiming, and raw bulk transfers.
 * Both ADB and Fastboot protocols build on top of this transport.
 */
/**
 * Size of the internal buffer used for USB transferIn calls.
 * Must be large enough to hold any single USB transfer the device might send.
 * ADB and Fastboot both send packets well under 16 KB.
 */
const USB_RECEIVE_BUFFER_SIZE = 16384;
class WebUsbTransport {
    _device;
    _inEndpoint = 0;
    _outEndpoint = 0;
    _interfaceNumber = 0;
    _opened = false;
    _filter;
    /** Internal buffer for excess bytes received from USB transfers. */
    _rxBuf = new Uint8Array(0);
    constructor(device, filter) {
        this._device = device;
        this._filter = filter;
    }
    // ---- Static Factory Methods ----
    /**
     * Prompt the user to select a USB device matching the given filter.
     * Requires a user gesture (click/tap) in the browser.
     */
    static async requestDevice(filter) {
        try {
            const device = await navigator.usb.requestDevice({
                filters: [filter],
            });
            return new WebUsbTransport(device, filter);
        }
        catch (e) {
            throw new UsbError(`Failed to request USB device: ${e.message || e}`, e);
        }
    }
    /**
     * Find an already-paired USB device matching the filter.
     * Does not require a user gesture.
     */
    static async findDevice(filter) {
        const devices = await navigator.usb.getDevices();
        for (const device of devices) {
            if (WebUsbTransport.matchesFilter(device, filter)) {
                return new WebUsbTransport(device, filter);
            }
        }
        return null;
    }
    /**
     * Get all paired USB devices matching the filter.
     */
    static async getDevices(filter) {
        const devices = await navigator.usb.getDevices();
        return devices.filter((d) => WebUsbTransport.matchesFilter(d, filter));
    }
    // ---- Connection Management ----
    /**
     * Open the device, select configuration, claim interface, and find endpoints.
     */
    async open(options) {
        if (this._opened)
            return;
        try {
            await this._device.open();
            // Select configuration (usually configuration 1)
            if (this._device.configuration === null) {
                await this._device.selectConfiguration(1);
            }
            // Find the matching interface and endpoints
            const endpoints = this.findEndpoints();
            this._inEndpoint = endpoints.inEndpoint;
            this._outEndpoint = endpoints.outEndpoint;
            this._interfaceNumber = endpoints.interfaceNumber;
            // Claim the interface
            await this._device.claimInterface(this._interfaceNumber);
            // Select the alternate setting that has the bulk endpoints.
            // Some devices (e.g. Pixel 7) have alternate 0 with no endpoints
            // and alternate 1 with the actual bulk IN/OUT endpoints.
            if (endpoints.alternateSetting !== 0) {
                await this._device.selectAlternateInterface(this._interfaceNumber, endpoints.alternateSetting);
            }
            // Clear any stale halt condition on both endpoints.
            // Previous sessions that were interrupted (tab closed, USB unplugged)
            // can leave endpoints in a HALTED state, causing every subsequent
            // transferIn/transferOut to fail with "A transfer error has occurred".
            // Some bootloaders (e.g. Volla Tablet / MediaTek) break when clearHalt
            // is sent to non-halted endpoints — use skip_clear_halt in device config.
            if (!options?.skipClearHalt) {
                try {
                    await this._device.clearHalt("in", this._inEndpoint);
                }
                catch {
                    // clearHalt may fail if endpoint isn't halted — that's fine
                }
                try {
                    await this._device.clearHalt("out", this._outEndpoint);
                }
                catch {
                    // clearHalt may fail if endpoint isn't halted — that's fine
                }
            }
            this._rxBuf = new Uint8Array(0);
            this._opened = true;
            log(`Transport opened: ${this.productName} ` +
                `(in=${this._inEndpoint}, out=${this._outEndpoint}, ` +
                `iface=${this._interfaceNumber})`);
        }
        catch (e) {
            throw new UsbError(`Failed to open USB device: ${e.message || e}`, e);
        }
    }
    /**
     * Release the interface and close the device.
     */
    async close() {
        if (!this._opened)
            return;
        try {
            await this._device.releaseInterface(this._interfaceNumber);
            await this._device.close();
        }
        catch (e) {
            log(`Close warning: ${e.message || e}`);
        }
        finally {
            this._opened = false;
            this._rxBuf = new Uint8Array(0);
        }
    }
    /**
     * Reset the USB device. May help recover from stale state.
     */
    async reset() {
        try {
            await this._device.reset();
            log("USB device reset");
        }
        catch (e) {
            throw new UsbError(`USB device reset failed: ${e.message || e}`, e);
        }
    }
    /**
     * Close and re-open the USB connection for a fresh session.
     * Useful for recovering from degraded USB state (e.g., after flash timeouts).
     */
    async reconnect(settleMs = 2000) {
        log("Reconnecting USB session...");
        // Reset first to abort any pending transferIn/transferOut calls.
        // After a timeout, Promise.race leaves the underlying USB transfer
        // still active, which blocks releaseInterface() during close().
        try {
            await this._device.reset();
        }
        catch {
            // Reset may fail if device is already disconnected — that's OK
        }
        await this.close();
        // Wait for USB bus to stabilize after reset
        await new Promise((resolve) => setTimeout(resolve, settleMs));
        // Re-open the connection
        await this.open();
        log("USB session reconnected");
    }
    /**
     * Discard any buffered receive data. Call after a mode switch or error
     * recovery to avoid reading stale bytes.
     */
    flushReceiveBuffer() {
        this._rxBuf = new Uint8Array(0);
    }
    // ---- Data Transfer ----
    /**
     * Send raw bytes to the device via bulk OUT transfer.
     */
    async send(data) {
        if (!this._opened) {
            throw new UsbError("Transport not open");
        }
        const result = await this._device.transferOut(this._outEndpoint, data);
        if (result.status !== "ok") {
            throw new UsbError(`USB transferOut failed: status=${result.status}`);
        }
        if (result.bytesWritten !== undefined && result.bytesWritten !== data.byteLength) {
            throw new UsbError(`USB transferOut incomplete: wrote ${result.bytesWritten}/${data.byteLength} bytes`);
        }
    }
    /**
     * Receive exactly `length` bytes from the device.
     *
     * Uses an internal buffer so that USB transfers can be read with a large
     * buffer (preventing overflow errors when the device sends more bytes than
     * requested) and excess bytes are kept for subsequent reads.
     *
     * Use this for protocols that frame messages with known lengths (ADB).
     */
    async receive(length) {
        if (!this._opened) {
            throw new UsbError("Transport not open");
        }
        // Accumulate data until we have enough
        while (this._rxBuf.byteLength < length) {
            const fresh = await this.doTransferIn();
            if (fresh.byteLength === 0) {
                throw new UsbError("USB transferIn returned empty data");
            }
            const combined = new Uint8Array(this._rxBuf.byteLength + fresh.byteLength);
            combined.set(this._rxBuf, 0);
            combined.set(fresh, this._rxBuf.byteLength);
            this._rxBuf = combined;
        }
        // Return exactly the requested bytes, keep the rest buffered
        const result = this._rxBuf.slice(0, length);
        this._rxBuf = this._rxBuf.slice(length);
        return result;
    }
    /**
     * Read a single USB transfer (up to `maxLength` bytes).
     *
     * Does NOT wait until `maxLength` bytes arrive — returns whatever the
     * device sent in one transfer.  Use this for protocols with
     * variable-length, single-transfer responses (Fastboot).
     */
    async readTransfer(maxLength = USB_RECEIVE_BUFFER_SIZE) {
        if (!this._opened) {
            throw new UsbError("Transport not open");
        }
        // Drain any leftover buffered data first
        if (this._rxBuf.byteLength > 0) {
            const take = Math.min(maxLength, this._rxBuf.byteLength);
            const result = this._rxBuf.slice(0, take);
            this._rxBuf = this._rxBuf.slice(take);
            return result;
        }
        return this.doTransferIn(maxLength);
    }
    /**
     * Receive exactly `length` bytes with a timeout.
     * Throws TimeoutError if the data does not arrive in time.
     */
    async receiveWithTimeout(length, timeoutMs = DEFAULT_TIMEOUT_MS) {
        return Promise.race([
            this.receive(length),
            new Promise((_, reject) => {
                setTimeout(() => reject(new TimeoutError(`USB receive timed out after ${timeoutMs}ms`, timeoutMs)), timeoutMs);
            }),
        ]);
    }
    /**
     * Read a single USB transfer with a timeout.
     */
    async readTransferWithTimeout(maxLength = USB_RECEIVE_BUFFER_SIZE, timeoutMs = DEFAULT_TIMEOUT_MS) {
        return Promise.race([
            this.readTransfer(maxLength),
            new Promise((_, reject) => {
                setTimeout(() => reject(new TimeoutError(`USB receive timed out after ${timeoutMs}ms`, timeoutMs)), timeoutMs);
            }),
        ]);
    }
    /**
     * Send bytes with a timeout.
     */
    async sendWithTimeout(data, timeoutMs = DEFAULT_TIMEOUT_MS) {
        return Promise.race([
            this.send(data),
            new Promise((_, reject) => {
                setTimeout(() => reject(new TimeoutError(`USB send timed out after ${timeoutMs}ms`, timeoutMs)), timeoutMs);
            }),
        ]);
    }
    // ---- Getters ----
    get device() {
        return this._device;
    }
    get isOpen() {
        return this._opened;
    }
    get productName() {
        return this._device.productName ?? "";
    }
    get serialNumber() {
        return this._device.serialNumber ?? "";
    }
    // ---- Private Helpers ----
    /**
     * Perform a single USB bulk IN transfer with a large buffer.
     */
    async doTransferIn(bufferSize = USB_RECEIVE_BUFFER_SIZE) {
        const result = await this._device.transferIn(this._inEndpoint, bufferSize);
        if (result.status !== "ok") {
            throw new UsbError(`USB transferIn failed: status=${result.status}`);
        }
        if (!result.data || result.data.byteLength === 0) {
            return new Uint8Array(0);
        }
        return new Uint8Array(result.data.buffer, result.data.byteOffset, result.data.byteLength);
    }
    /**
     * Find IN and OUT bulk endpoints matching the configured USB filter.
     */
    findEndpoints() {
        const config = this._device.configuration;
        if (!config) {
            throw new UsbError("No USB configuration selected");
        }
        for (const iface of config.interfaces) {
            for (const alt of iface.alternates) {
                // Match the filter criteria
                const classMatch = this._filter.classCode === undefined ||
                    alt.interfaceClass === this._filter.classCode;
                const subclassMatch = this._filter.subclassCode === undefined ||
                    alt.interfaceSubclass === this._filter.subclassCode;
                const protocolMatch = this._filter.protocolCode === undefined ||
                    alt.interfaceProtocol === this._filter.protocolCode;
                if (classMatch && subclassMatch && protocolMatch) {
                    let inEndpoint = -1;
                    let outEndpoint = -1;
                    for (const ep of alt.endpoints) {
                        if (ep.type !== "bulk")
                            continue;
                        if (ep.direction === "in") {
                            inEndpoint = ep.endpointNumber;
                        }
                        else if (ep.direction === "out") {
                            outEndpoint = ep.endpointNumber;
                        }
                    }
                    if (inEndpoint >= 0 && outEndpoint >= 0) {
                        return {
                            inEndpoint,
                            outEndpoint,
                            interfaceNumber: iface.interfaceNumber,
                            alternateSetting: alt.alternateSetting,
                        };
                    }
                }
            }
        }
        throw new UsbError(`No matching USB interface found for filter ` +
            `(class=0x${this._filter.classCode?.toString(16)}, ` +
            `subclass=0x${this._filter.subclassCode?.toString(16)}, ` +
            `protocol=0x${this._filter.protocolCode?.toString(16)})`);
    }
    /**
     * Check if a USB device has at least one interface matching the filter.
     */
    static matchesFilter(device, filter) {
        // Check vendor/product ID filters
        if (filter.vendorId !== undefined && device.vendorId !== filter.vendorId) {
            return false;
        }
        if (filter.productId !== undefined &&
            device.productId !== filter.productId) {
            return false;
        }
        // Check interface class filters
        if (filter.classCode !== undefined ||
            filter.subclassCode !== undefined ||
            filter.protocolCode !== undefined) {
            const config = device.configuration;
            if (!config)
                return false;
            for (const iface of config.interfaces) {
                for (const alt of iface.alternates) {
                    const classMatch = filter.classCode === undefined ||
                        alt.interfaceClass === filter.classCode;
                    const subclassMatch = filter.subclassCode === undefined ||
                        alt.interfaceSubclass === filter.subclassCode;
                    const protocolMatch = filter.protocolCode === undefined ||
                        alt.interfaceProtocol === filter.protocolCode;
                    if (classMatch && subclassMatch && protocolMatch) {
                        return true;
                    }
                }
            }
            return false;
        }
        return true;
    }
}

/**
 * Fastboot protocol type definitions.
 */
/** Fastboot response status prefixes (4 ASCII bytes) */
var FastbootResponse;
(function (FastbootResponse) {
    FastbootResponse["Okay"] = "OKAY";
    FastbootResponse["Fail"] = "FAIL";
    FastbootResponse["Data"] = "DATA";
    FastbootResponse["Info"] = "INFO";
})(FastbootResponse || (FastbootResponse = {}));
// ---- Sparse Image Structures ----
/** Sparse image magic number: 0xED26FF3A */
const SPARSE_MAGIC = 0xed26ff3a;
/** Size of the sparse file header in bytes */
const SPARSE_HEADER_SIZE = 28;
/** Size of a sparse chunk header in bytes */
const SPARSE_CHUNK_HEADER_SIZE = 12;
/** Sparse chunk types */
var SparseChunkType;
(function (SparseChunkType) {
    SparseChunkType[SparseChunkType["Raw"] = 51905] = "Raw";
    SparseChunkType[SparseChunkType["Fill"] = 51906] = "Fill";
    SparseChunkType[SparseChunkType["DontCare"] = 51907] = "DontCare";
    SparseChunkType[SparseChunkType["Crc32"] = 51908] = "Crc32";
})(SparseChunkType || (SparseChunkType = {}));
/** Default fastboot command timeout (30 seconds) */
const FASTBOOT_COMMAND_TIMEOUT_MS = 30_000;
/** Extended timeout for flash operations (5 minutes) */
const FASTBOOT_FLASH_TIMEOUT_MS = 300_000;

/**
 * Low-level fastboot protocol implementation.
 *
 * Handles sending commands, reading responses, and transferring data
 * over the WebUSB transport layer using the fastboot protocol.
 *
 * Protocol:
 *  - Commands: ASCII string sent via bulk OUT (max 4096 bytes)
 *  - Responses: 4-byte status prefix (OKAY/FAIL/DATA/INFO) + message via bulk IN
 *  - Data transfer: download command → DATA response → raw bytes → OKAY
 */
const RESPONSE_PREFIX_LEN = 4;
const MAX_RESPONSE_SIZE = 4096;
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();
/**
 * Send a fastboot command string to the device.
 */
async function sendCommand(transport, command, timeoutMs = FASTBOOT_COMMAND_TIMEOUT_MS) {
    log(`fastboot > ${command}`);
    const encoded = textEncoder.encode(command);
    await transport.sendWithTimeout(encoded, timeoutMs);
    return readResponse(transport, timeoutMs);
}
/**
 * Read a fastboot response, consuming any INFO messages along the way.
 * Returns the final OKAY, FAIL, or DATA response.
 */
async function readResponse(transport, timeoutMs = FASTBOOT_COMMAND_TIMEOUT_MS) {
    // eslint-disable-next-line no-constant-condition
    while (true) {
        const data = await transport.readTransferWithTimeout(MAX_RESPONSE_SIZE, timeoutMs);
        const result = parseResponse(data);
        log(`fastboot < ${result.status} ${result.message}`);
        // INFO responses are intermediate status messages — log and continue
        if (result.status === FastbootResponse.Info) {
            continue;
        }
        // FAIL responses become a ProtocolError
        if (result.status === FastbootResponse.Fail) {
            throw new ProtocolError(`Fastboot command failed: ${result.message}`, {
                bootloaderMessage: result.message,
            });
        }
        return result;
    }
}
/**
 * Send raw data to the device in chunks with progress reporting.
 * Used after receiving a DATA response to a download command.
 */
async function sendData(transport, data, onProgress, chunkSize = 512 * 1024, timeoutMs = FASTBOOT_COMMAND_TIMEOUT_MS) {
    const total = data.byteLength;
    let offset = 0;
    while (offset < total) {
        const end = Math.min(offset + chunkSize, total);
        const chunk = data.subarray(offset, end);
        await transport.sendWithTimeout(chunk, timeoutMs);
        offset = end;
        onProgress?.(offset, total);
        // Yield to the browser event loop between chunks so Chrome's USB
        // stack can process completion events and hardware ACKs. Without
        // this, back-to-back transferOut calls can starve the USB driver's
        // completion handler, causing the device to miss data.
        if (offset < total) {
            await new Promise((resolve) => setTimeout(resolve, 0));
        }
    }
}
/**
 * Download a blob to the device memory (download command + data transfer).
 * This does NOT flash — call flashPartition() after downloading.
 */
async function downloadData(transport, data, onProgress, timeoutMs = FASTBOOT_COMMAND_TIMEOUT_MS) {
    const sizeHex = data.byteLength.toString(16).padStart(8, "0");
    const command = `download:${sizeHex}`;
    log(`fastboot > ${command} (${data.byteLength} bytes)`);
    const encoded = textEncoder.encode(command);
    await transport.sendWithTimeout(encoded, timeoutMs);
    // Expect DATA response with the size
    const response = await readResponse(transport, timeoutMs);
    if (response.status !== FastbootResponse.Data) {
        throw new ProtocolError(`Expected DATA response for download, got ${response.status}: ${response.message}`);
    }
    // Send the raw data
    await sendData(transport, data, onProgress, 512 * 1024, timeoutMs);
    // Let the device fully process the received data before we issue a
    // USB IN transfer for the OKAY response. Chrome's async transferOut
    // resolves when the host controller accepts the data, but the device
    // may still be DMA-ing the last packets. Issuing transferIn too early
    // can cause some bootloaders (Qualcomm ABL) to miss the response.
    await new Promise((resolve) => setTimeout(resolve, 250));
    // Read final OKAY
    await readResponse(transport, timeoutMs);
}
/**
 * Flash the previously downloaded data to a partition.
 */
async function flashPartition(transport, partition, timeoutMs = FASTBOOT_COMMAND_TIMEOUT_MS) {
    await sendCommand(transport, `flash:${partition}`, timeoutMs);
}
/**
 * Erase a partition.
 */
async function erasePartition(transport, partition, timeoutMs = FASTBOOT_COMMAND_TIMEOUT_MS) {
    await sendCommand(transport, `erase:${partition}`, timeoutMs);
}
/**
 * Get a bootloader variable value.
 */
async function getVariable(transport, name, timeoutMs = FASTBOOT_COMMAND_TIMEOUT_MS) {
    const result = await sendCommand(transport, `getvar:${name}`, timeoutMs);
    return result.message;
}
// ---- Internal Helpers ----
/**
 * Parse a raw fastboot response buffer into a structured result.
 */
function parseResponse(data) {
    if (data.byteLength < RESPONSE_PREFIX_LEN) {
        throw new ProtocolError(`Fastboot response too short: ${data.byteLength} bytes`);
    }
    const prefix = textDecoder.decode(data.subarray(0, RESPONSE_PREFIX_LEN));
    const message = textDecoder.decode(data.subarray(RESPONSE_PREFIX_LEN)).trim();
    switch (prefix) {
        case FastbootResponse.Okay:
            return { status: FastbootResponse.Okay, message };
        case FastbootResponse.Fail:
            return { status: FastbootResponse.Fail, message };
        case FastbootResponse.Info:
            return { status: FastbootResponse.Info, message };
        case FastbootResponse.Data: {
            // DATA response: the message is a hex string representing the data size
            const dataSize = parseInt(message, 16);
            return { status: FastbootResponse.Data, message, dataSize };
        }
        default:
            throw new ProtocolError(`Unknown fastboot response prefix: "${prefix}"`);
    }
}

/**
 * Android sparse image format handling.
 *
 * Sparse images compress large partition images by omitting empty/dont-care
 * regions. This module detects, parses, and splits sparse images for devices
 * with limited download buffer sizes.
 *
 * Format:
 *  - 28-byte file header (magic, version, block/chunk counts)
 *  - Sequence of chunks, each with a 12-byte header + optional data
 *  - Chunk types: RAW (0xCAC1), FILL (0xCAC2), DONT_CARE (0xCAC3), CRC32 (0xCAC4)
 */
/**
 * Check if a buffer starts with the sparse image magic number.
 */
function isSparseImage(header) {
    if (header.byteLength < 4)
        return false;
    const view = new DataView(header.buffer, header.byteOffset, header.byteLength);
    return view.getUint32(0, true) === SPARSE_MAGIC;
}
/**
 * Parse the 28-byte sparse image file header.
 */
function parseSparseHeader(data) {
    if (data.byteLength < SPARSE_HEADER_SIZE) {
        throw new Error(`Sparse header too short: ${data.byteLength} < ${SPARSE_HEADER_SIZE}`);
    }
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    const magic = view.getUint32(0, true);
    if (magic !== SPARSE_MAGIC) {
        throw new Error(`Not a sparse image: magic=0x${magic.toString(16)}, expected 0x${SPARSE_MAGIC.toString(16)}`);
    }
    return {
        magic,
        majorVersion: view.getUint16(4, true),
        minorVersion: view.getUint16(6, true),
        fileHeaderSize: view.getUint16(8, true),
        chunkHeaderSize: view.getUint16(10, true),
        blockSize: view.getUint32(12, true),
        totalBlocks: view.getUint32(16, true),
        totalChunks: view.getUint32(20, true),
        imageChecksum: view.getUint32(24, true),
    };
}
/**
 * Parse a 12-byte sparse chunk header.
 */
function parseChunkHeader(data) {
    if (data.byteLength < SPARSE_CHUNK_HEADER_SIZE) {
        throw new Error(`Chunk header too short: ${data.byteLength} < ${SPARSE_CHUNK_HEADER_SIZE}`);
    }
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    return {
        type: view.getUint16(0, true),
        chunkBlocks: view.getUint32(4, true),
        totalSize: view.getUint32(8, true),
    };
}
/**
 * Calculate the data size following a chunk header based on chunk type.
 */
function chunkDataSize(chunk, blockSize) {
    switch (chunk.type) {
        case SparseChunkType.Raw:
            return chunk.chunkBlocks * blockSize;
        case SparseChunkType.Fill:
            return 4; // 4-byte fill pattern
        case SparseChunkType.DontCare:
            return 0;
        case SparseChunkType.Crc32:
            return 4; // 4-byte CRC32
        default:
            throw new Error(`Unknown sparse chunk type: 0x${chunk.type.toString(16)}`);
    }
}
/**
 * Build a sparse image file header from parameters.
 */
function buildSparseHeader(blockSize, totalBlocks, totalChunks) {
    const buf = new ArrayBuffer(SPARSE_HEADER_SIZE);
    const view = new DataView(buf);
    view.setUint32(0, SPARSE_MAGIC, true);
    view.setUint16(4, 1, true); // major version
    view.setUint16(6, 0, true); // minor version
    view.setUint16(8, SPARSE_HEADER_SIZE, true); // file header size
    view.setUint16(10, SPARSE_CHUNK_HEADER_SIZE, true); // chunk header size
    view.setUint32(12, blockSize, true);
    view.setUint32(16, totalBlocks, true);
    view.setUint32(20, totalChunks, true);
    view.setUint32(24, 0, true); // checksum (unused)
    return new Uint8Array(buf);
}
/**
 * Split a sparse image into multiple sub-images, each smaller than maxSize.
 *
 * This is needed when the device's max-download-size is smaller than the
 * sparse image. Each sub-image is a valid sparse image that can be downloaded
 * and flashed independently.
 *
 * Each sub-image after the first includes a DONT_CARE chunk at the start to
 * skip the blocks already written by previous sub-images, so the device
 * writes each sub-image's data at the correct partition offset.
 *
 * Each sub-image's header totalBlocks = blocksOffset + dataBlocks, so the
 * chunk block sum matches the header (required by MediaTek LK and other
 * bootloaders that validate this).
 */
async function splitSparseImage(blob, maxSize) {
    const headerBuf = new Uint8Array(await blob.slice(0, SPARSE_HEADER_SIZE).arrayBuffer());
    const header = parseSparseHeader(headerBuf);
    const chunks = [];
    let offset = header.fileHeaderSize;
    for (let i = 0; i < header.totalChunks; i++) {
        const chunkHeaderBuf = new Uint8Array(await blob.slice(offset, offset + SPARSE_CHUNK_HEADER_SIZE).arrayBuffer());
        const chunkHeader = parseChunkHeader(chunkHeaderBuf);
        const dataSize = chunkDataSize(chunkHeader, header.blockSize);
        chunks.push({
            header: chunkHeader,
            offset,
            blocks: chunkHeader.chunkBlocks,
        });
        offset += SPARSE_CHUNK_HEADER_SIZE + dataSize;
    }
    // If the whole image fits, return it as-is
    if (blob.size <= maxSize) {
        return [blob];
    }
    // Group chunks into sub-images that fit within maxSize.
    // Each sub-image after the first reserves space for a DONT_CARE prefix chunk.
    const subImages = [];
    let currentChunks = [];
    let currentSize = SPARSE_HEADER_SIZE;
    let currentBlocks = 0;
    let blocksWrittenSoFar = 0;
    for (const chunk of chunks) {
        const dataSize = chunkDataSize(chunk.header, header.blockSize);
        const chunkTotalSize = SPARSE_CHUNK_HEADER_SIZE + dataSize;
        // If adding this chunk would exceed maxSize, finalize current sub-image
        if (currentChunks.length > 0 &&
            currentSize + chunkTotalSize > maxSize) {
            subImages.push(buildSubImage(blob, header.blockSize, header.totalBlocks, currentChunks, blocksWrittenSoFar));
            blocksWrittenSoFar += currentBlocks;
            currentChunks = [];
            // Reserve space for the DONT_CARE prefix chunk in subsequent sub-images
            currentSize = SPARSE_HEADER_SIZE + SPARSE_CHUNK_HEADER_SIZE;
            currentBlocks = 0;
        }
        currentChunks.push(chunk);
        currentSize += chunkTotalSize;
        currentBlocks += chunk.blocks;
    }
    // Finalize the last sub-image
    if (currentChunks.length > 0) {
        subImages.push(buildSubImage(blob, header.blockSize, header.totalBlocks, currentChunks, blocksWrittenSoFar));
    }
    return subImages;
}
/**
 * Build a sub-image Blob from a subset of chunks.
 *
 * @param originalTotalBlocks  The ORIGINAL image's total block count.
 * @param blocksOffset Blocks already written by previous sub-images.
 *                     A DONT_CARE chunk is prepended to skip these blocks.
 */
function buildSubImage(originalBlob, blockSize, originalTotalBlocks, chunks, blocksOffset) {
    const hasDontCarePrefix = blocksOffset > 0;
    const numChunks = chunks.length + (hasDontCarePrefix ? 1 : 0);
    // totalBlocks for this sub-image = offset blocks + data blocks.
    // The bootloader validates that chunk blocks sum to totalBlocks.
    const dataBlocks = chunks.reduce((sum, c) => sum + c.blocks, 0);
    const subImageTotalBlocks = blocksOffset + dataBlocks;
    const newHeader = buildSparseHeader(blockSize, subImageTotalBlocks, numChunks);
    const parts = [newHeader];
    // Prepend a DONT_CARE chunk to skip blocks written by previous sub-images
    if (hasDontCarePrefix) {
        parts.push(buildDontCareChunk(blocksOffset));
    }
    for (const chunk of chunks) {
        const dataSize = chunkDataSize(chunk.header, blockSize);
        const chunkTotalSize = SPARSE_CHUNK_HEADER_SIZE + dataSize;
        // Slice the original chunk (header + data) from the source blob
        parts.push(originalBlob.slice(chunk.offset, chunk.offset + chunkTotalSize));
    }
    return new Blob(parts);
}
/**
 * Build a 12-byte DONT_CARE chunk header.
 * Used to skip blocks already written by previous sub-images.
 */
function buildDontCareChunk(chunkBlocks) {
    const buf = new ArrayBuffer(SPARSE_CHUNK_HEADER_SIZE);
    const view = new DataView(buf);
    view.setUint16(0, SparseChunkType.DontCare, true);
    view.setUint16(2, 0, true); // reserved
    view.setUint32(4, chunkBlocks, true);
    view.setUint32(8, SPARSE_CHUNK_HEADER_SIZE, true); // total size = header only
    return new Uint8Array(buf);
}

/**
 * High-level Fastboot device interface.
 *
 * Provides the public API for connecting to a device in bootloader/fastboot
 * mode and performing operations like flashing, erasing, and rebooting.
 * Handles sparse image detection and splitting transparently.
 */
class FastbootDevice {
    _transport;
    _connected = false;
    _maxDownloadSize = null;
    _currentSlot = null;
    constructor(transport) {
        this._transport = transport;
    }
    // ---- Static Factory Methods ----
    /**
     * Prompt the user to select a fastboot device.
     * Requires a user gesture (click/tap).
     */
    static async requestDevice() {
        const transport = await WebUsbTransport.requestDevice(FASTBOOT_USB_FILTER);
        return new FastbootDevice(transport);
    }
    /**
     * Find an already-paired fastboot device without user gesture.
     * Returns null if no paired fastboot device is found.
     */
    static async findDevice() {
        const transport = await WebUsbTransport.findDevice(FASTBOOT_USB_FILTER);
        if (!transport)
            return null;
        return new FastbootDevice(transport);
    }
    // ---- Connection ----
    /**
     * Open the USB connection and verify the device speaks fastboot.
     */
    async connect(options) {
        if (this._connected)
            return;
        await this._transport.open(options);
        // Verify fastboot protocol with a handshake
        try {
            const version = await getVariable(this._transport, "version");
            log(`Fastboot connected, protocol version: ${version}`);
        }
        catch {
            // Some devices don't support getvar:version, that's okay
            log("Fastboot connected (version query not supported)");
        }
        this._connected = true;
    }
    /**
     * Close the USB connection.
     */
    async disconnect() {
        if (!this._connected)
            return;
        await this._transport.close();
        this._connected = false;
        this._maxDownloadSize = null;
        this._currentSlot = null;
    }
    // ---- Commands ----
    /**
     * Get a bootloader variable (e.g., "version", "product", "unlocked").
     */
    async getVariable(name) {
        this.ensureConnected();
        return getVariable(this._transport, name);
    }
    /**
     * Run an arbitrary fastboot command and return the response message.
     * Used for commands like "flashing unlock", "oem unlock", "flashing lock", etc.
     */
    async runCommand(command, timeoutMs) {
        this.ensureConnected();
        const result = await sendCommand(this._transport, command, timeoutMs);
        return result.message;
    }
    /**
     * Flash a blob to a partition.
     *
     * Automatically detects sparse images and splits them if they exceed
     * the device's max-download-size. Reports progress via callback.
     * Resolves A/B slot suffix automatically when needed.
     */
    async flashBlob(partition, blob, onProgress) {
        this.ensureConnected();
        const resolved = await this.resolvePartition(partition);
        // Read the first few bytes to check for sparse format
        const headerBytes = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
        if (isSparseImage(headerBytes)) {
            await this.flashSparseBlob(resolved, blob, onProgress);
        }
        else {
            await this.flashRawBlob(resolved, blob, onProgress);
        }
    }
    /**
     * Erase a partition.
     * Resolves A/B slot suffix automatically when needed.
     */
    async erase(partition) {
        this.ensureConnected();
        const resolved = await this.resolvePartition(partition);
        await erasePartition(this._transport, resolved);
    }
    /**
     * Boot a blob without flashing (fastboot boot).
     */
    async bootBlob(blob) {
        this.ensureConnected();
        const data = new Uint8Array(await blob.arrayBuffer());
        await downloadData(this._transport, data);
        await sendCommand(this._transport, "boot");
    }
    /**
     * Reboot the device.
     * @param mode - "" for normal, "bootloader" for fastboot, "recovery", etc.
     */
    async reboot(mode) {
        this.ensureConnected();
        const command = mode ? `reboot-${mode}` : "reboot";
        try {
            await sendCommand(this._transport, command, 5000);
        }
        catch {
            // Reboot often causes USB disconnect before response arrives
            log(`Reboot command sent (${command}), device may have disconnected`);
        }
        this._connected = false;
    }
    /**
     * Reset the underlying USB device.
     */
    async resetDevice() {
        await this._transport.reset();
    }
    /**
     * Close and re-open the USB connection for a fresh session.
     */
    async reconnect() {
        this._connected = false;
        this._maxDownloadSize = null;
        this._currentSlot = null;
        await this._transport.reconnect();
        this._connected = true;
    }
    // ---- Getters ----
    get isConnected() {
        return this._connected;
    }
    get usbDevice() {
        return this._transport.device;
    }
    // ---- Private Helpers ----
    ensureConnected() {
        if (!this._connected) {
            throw new UsbError("Fastboot device not connected");
        }
    }
    /**
     * Get and cache the device's max-download-size.
     * Falls back to 512 MB if the variable is not available.
     *
     * Bootloaders vary in format:
     *   - Qualcomm ABL: decimal string ("805306368" = 768 MB)
     *   - MediaTek/Google: hex with 0x prefix ("0x30000000" = 768 MB)
     * Matches AOSP fastboot's strtoll(str, NULL, 0) behavior: 0x prefix
     * means hex, otherwise decimal.
     */
    async getMaxDownloadSize() {
        if (this._maxDownloadSize !== null)
            return this._maxDownloadSize;
        try {
            const value = await getVariable(this._transport, "max-download-size");
            if (value.startsWith("0x") || value.startsWith("0X")) {
                this._maxDownloadSize = parseInt(value, 16);
            }
            else {
                this._maxDownloadSize = parseInt(value, 10);
            }
            if (isNaN(this._maxDownloadSize) || this._maxDownloadSize <= 0) {
                this._maxDownloadSize = 512 * 1024 * 1024;
            }
        }
        catch {
            // Default to 512 MB
            this._maxDownloadSize = 512 * 1024 * 1024;
        }
        log(`Max download size: ${this._maxDownloadSize} bytes`);
        return this._maxDownloadSize;
    }
    /**
     * Resolve a partition name by appending the current A/B slot suffix
     * if the device reports the partition is slotted (getvar:has-slot).
     * Partitions that already have a slot suffix (_a/_b) are returned as-is.
     */
    async resolvePartition(partition) {
        if (partition.endsWith("_a") || partition.endsWith("_b")) {
            return partition;
        }
        try {
            const hasSlot = await getVariable(this._transport, `has-slot:${partition}`);
            if (hasSlot === "yes") {
                const slot = await this.getCurrentSlot();
                const resolved = `${partition}_${slot}`;
                log(`Partition ${partition} → ${resolved} (slot=${slot})`);
                return resolved;
            }
        }
        catch {
            // getvar:has-slot not supported — use partition name as-is
        }
        return partition;
    }
    /**
     * Get and cache the device's current A/B slot.
     */
    async getCurrentSlot() {
        if (this._currentSlot !== null)
            return this._currentSlot;
        try {
            this._currentSlot = await getVariable(this._transport, "current-slot");
            // Some bootloaders return "a" or "b", others return "_a" or "_b"
            this._currentSlot = this._currentSlot.replace(/^_/, "");
        }
        catch {
            this._currentSlot = "a";
        }
        log(`Current slot: ${this._currentSlot}`);
        return this._currentSlot;
    }
    /**
     * Flash a raw (non-sparse) blob: download + flash.
     */
    async flashRawBlob(partition, blob, onProgress) {
        const data = new Uint8Array(await blob.arrayBuffer());
        await downloadData(this._transport, data, onProgress, FASTBOOT_FLASH_TIMEOUT_MS);
        await flashPartition(this._transport, partition, FASTBOOT_FLASH_TIMEOUT_MS);
        await this.waitDeviceReady();
    }
    /**
     * Flash a sparse blob: split if needed, then download + flash each sub-image.
     */
    async flashSparseBlob(partition, blob, onProgress) {
        const maxSize = await this.getMaxDownloadSize();
        const subImages = await splitSparseImage(blob, maxSize);
        log(`Flashing sparse image to ${partition}: ` +
            `${subImages.length} sub-image(s), total ${blob.size} bytes`);
        const totalSize = subImages.reduce((sum, img) => sum + img.size, 0);
        let sentSoFar = 0;
        for (let i = 0; i < subImages.length; i++) {
            const subImage = subImages[i];
            const data = new Uint8Array(await subImage.arrayBuffer());
            const subImageSize = data.byteLength;
            await downloadData(this._transport, data, (sent) => {
                onProgress?.(sentSoFar + sent, totalSize);
            }, FASTBOOT_FLASH_TIMEOUT_MS);
            await flashPartition(this._transport, partition, FASTBOOT_FLASH_TIMEOUT_MS);
            sentSoFar += subImageSize;
            log(`Sparse sub-image ${i + 1}/${subImages.length} flashed ` +
                `(${subImageSize} bytes)`);
        }
        await this.waitDeviceReady();
    }
    /**
     * Verify the device is responsive after a flash operation.
     * Some bootloaders (Qualcomm ABL) continue internal processing after
     * sending OKAY for a flash command. Starting the next download before
     * this finishes can cause the device to hang without responding.
     * A quick getvar round-trip acts as a synchronization barrier.
     */
    async waitDeviceReady() {
        try {
            await getVariable(this._transport, "product", 5000);
        }
        catch {
            // FAIL or timeout — either way, the device had time to settle
        }
    }
}

export { ADB_USB_FILTER, DEFAULT_TIMEOUT_MS, DeviceError, DeviceMode, FASTBOOT_USB_FILTER, FastbootDevice, LogLevel, MAX_TRANSFER_SIZE, ProtocolError, TimeoutError, UsbError, WebUsbTransport, getLogLevel, isSparseImage, log, logError, setLogLevel, splitSparseImage };
//# sourceMappingURL=fastboot.mjs.map

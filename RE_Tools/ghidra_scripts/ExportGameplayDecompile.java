// Export decompiled gameplay functions for HorseSDK (Horsey.exe).
//
// Targets (RVA, image base 0x140000000):
//   GainMoney      @ 0x10AB80 (function entry)
//   SimSpawnDisk   @ 0x342F0 (string xref -> exports FUN @ 0x33A20)
//   BuyItem        @ 0x78B00 (string xref -> exports FUN @ 0x787D0)
//   Race cluster   @ 0x90E00 .. 0x92000 + RaceStateMachine @ 0x8F2B0
//
// GUI: Script Manager -> Run; set output dir when prompted (or pass arg).
// Headless:
//   analyzeHeadless <projectDir> HorseSDK -import Game/Horsey.exe -overwrite \
//     -scriptPath RE_Tools/ghidra_scripts \
//     -postScript ExportGameplayDecompile.java "<abs>/RE_Tools/docs/ghidra_exports"
//
//@category HorseSDK
//@menupath HorseSDK.Export Gameplay Decompile

import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.symbol.SourceType;
import ghidra.util.task.TaskMonitor;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.List;

public class ExportGameplayDecompile extends GhidraScript {

    private static final long IMAGE_BASE = 0x140000000L;

    private static class Target {
        final long rva;
        final String name;
        final String note;

        Target(long rva, String name, String note) {
            this.rva = rva;
            this.name = name;
            this.note = note;
        }
    }

    private static final Target[] PINNED = {
        new Target(0x10AB80L, "GainMoney",
            "void GainMoney(ctx, amount, flag): [ctx+0x308]+=edx; [ctx+0x30c]=0x3c"),
        new Target(0x342F0L, "SimSpawnDisk",
            "World spawn: alloc tag 'SimSpawnDisk', place via [rbx+0x148]"),
        new Target(0x78B00L, "BuyItem",
            "Shop buy dispatch; calls helper @ 0x21E450"),
    };

    private static final long RACE_CLUSTER_START = 0x90E00L;
    private static final long RACE_CLUSTER_END = 0x92000L;

    @Override
    public void run() throws Exception {
        if (currentProgram == null) {
            popup("No program loaded.");
            return;
        }

        File outDir = resolveOutputDir();
        if (outDir == null) {
            popup("No output directory.");
            return;
        }
        if (!outDir.isDirectory() && !outDir.mkdirs()) {
            popup("Cannot create output directory: " + outDir.getAbsolutePath());
            return;
        }

        Listing listing = currentProgram.getListing();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);

        try {
            for (Target t : PINNED) {
                exportOne(listing, decomp, outDir, t);
            }
            exportRaceCluster(listing, decomp, outDir);
            popup("Wrote exports to:\n" + outDir.getAbsolutePath());
        } finally {
            decomp.dispose();
        }
    }

    private File resolveOutputDir() throws Exception {
        String[] args = getScriptArgs();
        if (args != null && args.length > 0 && args[0] != null && !args[0].isEmpty()) {
            return new File(args[0]);
        }
        String picked = askString("Output directory",
            "Path to RE_Tools/docs/ghidra_exports (folder must exist or will be created)");
        if (picked == null || picked.isEmpty()) {
            return null;
        }
        return new File(picked);
    }

    private Address rvaToAddr(long rva) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(IMAGE_BASE + rva);
    }

    private void ensureLabel(Address addr, String name) {
        try {
            currentProgram.getSymbolTable().createLabel(addr, name, SourceType.USER_DEFINED);
        } catch (Exception e) {
            // label may already exist
        }
    }

    private Function ensureFunction(Listing listing, Address entry, String name) throws Exception {
        ensureLabel(entry, name);
        Function func = listing.getFunctionAt(entry);
        if (func != null) {
            return func;
        }
        func = getFunctionContaining(entry);
        if (func != null) {
            return func;
        }
        // CreateFunctionCmd works across Ghidra 10.x / 11.x (createFunction return type varies)
        CreateFunctionCmd cmd = new CreateFunctionCmd(entry);
        cmd.applyTo(currentProgram, monitor);
        func = listing.getFunctionAt(entry);
        if (func == null) {
            func = getFunctionContaining(entry);
        }
        if (func != null && name != null && !name.isEmpty()) {
            func.setName(name, SourceType.USER_DEFINED);
        }
        return func;
    }

    private Function resolveAt(Listing listing, Address at, String name) throws Exception {
        Function func = getFunctionContaining(at);
        if (func != null) {
            ensureLabel(at, name + "_xref");
            return func;
        }
        return ensureFunction(listing, at, name);
    }

    private void exportOne(Listing listing, DecompInterface decomp, File outDir, Target t)
            throws Exception {
        Address entry = rvaToAddr(t.rva);
        Function func = resolveAt(listing, entry, t.name);
        if (func == null) {
            printerr("No function at " + t.name + " " + entry);
            writeError(outDir, t.name, t, "createFunction failed at " + entry);
            return;
        }

        String body = decompile(decomp, func);
        String disasm = getDisassembly(func, 64);
        long entryRva = func.getEntryPoint().getOffset() - IMAGE_BASE;

        File out = new File(outDir, t.name + ".c.txt");
        try (PrintWriter pw = new PrintWriter(new FileWriter(out))) {
            writeHeader(pw, t.name, entryRva, func, t.note);
            pw.println();
            pw.println("/* --- Decompiler --- */");
            pw.println(body);
            pw.println();
            pw.println("/* --- Disassembly (head) --- */");
            pw.println(disasm);
        }
        println("Wrote " + out.getAbsolutePath());
    }

    private void exportRaceCluster(Listing listing, DecompInterface decomp, File outDir)
            throws Exception {
        Address start = rvaToAddr(RACE_CLUSTER_START);
        Address end = rvaToAddr(RACE_CLUSTER_END);
        AddressSet set = new AddressSet(start, end);

        List<Function> funcs = new ArrayList<>();
        FunctionIterator it = listing.getFunctions(set, true);
        while (it.hasNext()) {
            funcs.add(it.next());
        }
        Collections.sort(funcs, Comparator.comparing(f -> f.getEntryPoint()));

        File out = new File(outDir, "RaceCluster.c.txt");
        try (PrintWriter pw = new PrintWriter(new FileWriter(out))) {
            pw.println("# Ghidra export: Race UI cluster");
            pw.println("# RVA range: 0x" + Long.toHexString(RACE_CLUSTER_START)
                + " .. 0x" + Long.toHexString(RACE_CLUSTER_END));
            pw.println("# Image base 0x" + Long.toHexString(IMAGE_BASE));
            pw.println("# Functions in range: " + funcs.size());
            pw.println("# Generated: " + new SimpleDateFormat("yyyy-MM-dd").format(new Date()));
            pw.println("# Strings in cluster: RaceGo, WonRace, CrossFinishLine, OnYourMark, ...");
            pw.println();

            if (funcs.isEmpty()) {
                pw.println("/* No functions found — run Auto Analyze, then re-run script. */");
                pw.println("/* Or create functions manually at 0x91148, 0x9177B, etc. */");
            }

            for (Function func : funcs) {
                long rva = func.getEntryPoint().getOffset() - IMAGE_BASE;
                String fname = func.getName();
                pw.println("/* ========== " + fname + " @ 0x" + Long.toHexString(rva) + " ========== */");
                pw.println();
                pw.println(decompile(decomp, func));
                pw.println();
                pw.println("/* --- disasm head --- */");
                pw.println(getDisassembly(func, 48));
                pw.println();
            }
        }
        println("Wrote " + out.getAbsolutePath() + " (" + funcs.size() + " functions)");

        // Also export largest / named race handlers individually
        String[] prefer = {"RaceGo", "WonRace", "CrossFinishLine", "OnYourMark", "RaceGetSet"};
        for (String pname : prefer) {
            for (Function func : funcs) {
                if (func.getName().equalsIgnoreCase(pname)
                    || func.getName().contains(pname)) {
                    long rva = func.getEntryPoint().getOffset() - IMAGE_BASE;
                    Target t = new Target(rva, pname, "Race cluster export");
                    writeNamedFromFunction(decomp, outDir, t, func);
                    break;
                }
            }
        }
        // Pin by string-xref RVAs (export containing function, not necessarily entry at RVA)
        long[][] known = {
            {0x91148L}, {0x9177BL}, {0x912F9L}, {0x90E1BL}, {0x2DAE7L},
            {0x8F2B0L},  // main race state machine (contains most race string refs)
        };
        for (long[] row : known) {
            long xref = row[0];
            Address a = rvaToAddr(xref);
            Function f = getFunctionContaining(a);
            if (f == null) {
                f = ensureFunction(listing, a, "RaceFn_" + Long.toHexString(xref));
            }
            if (f != null) {
                long entryRva = f.getEntryPoint().getOffset() - IMAGE_BASE;
                String nm = (xref == 0x8F2B0L) ? "RaceStateMachine"
                    : "Race_" + Long.toHexString(xref);
                Target t = new Target(entryRva, nm,
                    "Contains xref @ 0x" + Long.toHexString(xref));
                File fout = new File(outDir, nm + ".c.txt");
                if (!fout.exists()) {
                    writeNamedFromFunction(decomp, outDir, t, f);
                }
            }
        }
    }

    private void writeNamedFromFunction(DecompInterface decomp, File outDir, Target t, Function func)
            throws Exception {
        long entryRva = func.getEntryPoint().getOffset() - IMAGE_BASE;
        File out = new File(outDir, t.name + ".c.txt");
        try (PrintWriter pw = new PrintWriter(new FileWriter(out))) {
            writeHeader(pw, t.name, entryRva, func, t.note);
            pw.println();
            pw.println(decompile(decomp, func));
            pw.println();
            pw.println("/* --- disasm head --- */");
            pw.println(getDisassembly(func, 48));
        }
        println("Wrote " + out.getAbsolutePath());
    }

    private void writeError(File outDir, String name, Target t, String err) throws Exception {
        File out = new File(outDir, name + ".c.txt");
        try (PrintWriter pw = new PrintWriter(new FileWriter(out))) {
            writeHeader(pw, name, t.rva, null, t.note);
            pw.println("/* ERROR: " + err + " */");
        }
    }

    private void writeHeader(PrintWriter pw, String name, long entryRva, Function func, String note) {
        pw.println("# Ghidra export: " + name);
        pw.println("# Requested RVA: 0x" + Long.toHexString(entryRva));
        if (func != null) {
            pw.println("# Function entry: " + func.getEntryPoint() + " (" + func.getName() + ")");
            pw.println("# Body: " + func.getBody());
        }
        pw.println("# Image base: 0x" + Long.toHexString(IMAGE_BASE));
        pw.println("# Program: " + currentProgram.getName());
        pw.println("# Note: " + note);
    }

    private String decompile(DecompInterface decomp, Function func) {
        DecompileResults res = decomp.decompileFunction(func, 60, TaskMonitor.DUMMY);
        if (res == null || !res.decompileCompleted()) {
            return "/* Decompile failed: "
                + (res != null ? res.getErrorMessage() : "null") + " */";
        }
        if (res.getDecompiledFunction() == null) {
            return "/* No decompiled function */";
        }
        return res.getDecompiledFunction().getC();
    }

    private String getDisassembly(Function func, int maxInsns) {
        StringBuilder sb = new StringBuilder();
        var listing = currentProgram.getListing();
        var ins = listing.getInstructions(func.getBody(), true);
        int n = 0;
        while (ins.hasNext() && n < maxInsns) {
            var i = ins.next();
            sb.append(i.getAddress()).append(": ").append(i).append("\n");
            n++;
        }
        return sb.toString();
    }
}

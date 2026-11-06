"""TXR Zero editor: dynamic garage within the verified SLUS-20189 card layout.
Part order: https://github.com/tofuman0/TXR0-Rival-Data
Additive game checksum matched against the supplied original; in-game testing pending.
"""
from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

DEFAULT = Path.home() / "save.mcd"
# Offsets relative to the start of each TYPE- name; 0xA0-byte records.
PERFORMANCE = [("Engine",35,7),("Muffler",36,8),("Transmission",37,4),
 ("Clutch & Diff",38,4),("Tires",39,9),("Brakes",40,9),
 ("Suspension",41,5),("Body",42,5)]
AERO = [("Front bumper",22,5),("Hood",23,2),("Mirror",24,2),
 ("Over fender",21,1),("Side skirt",25,5),("Rear bumper",26,5),
 ("Rear spoiler",27,5)]
PARTS = PERFORMANCE + AERO
GROUPS = {"A-Spec":["100TVM","R34RVM","SW20GT","A80RZM","ST205","R32RV2","Z15A","NA2"],
 "B-Spec":["S161VM","S13KKK","DE3A"],"C-Spec":["EG6","EK9"]}

# PS2 NAND spare/ECC format, corroborated against PCSX2 MemoryCardFile.cpp
# and Ross Ridge's public-domain mymc ECC algorithm.
_ECC_MASKS = (7,22,37,52,67,82,97,112)
_COLUMN = tuple(__import__('functools').reduce(int.__xor__,
    (_ECC_MASKS[i] for i in range(8) if b & (1<<i)),0) for b in range(256))
_PARITY = tuple(b.bit_count() & 1 for b in range(256))

def ecc128(chunk):
    column, line0, line1 = 0x77, 0x7f, 0x7f
    for i,b in enumerate(chunk):
        column ^= _COLUMN[b]
        if _PARITY[b]: line0 ^= (~i)&0x7f; line1 ^= i
    return bytes((column,line0,line1))

def encode_ps2(data):
    """512 data bytes + four 3-byte ECC codes + four erased spare bytes."""
    if len(data)!=67108864: raise ValueError("Expected a 64 MB SD2PSX image.")
    out=bytearray()
    for offset in range(0,len(data),512):
        page=data[offset:offset+512]
        out.extend(page)
        for j in range(0,512,128): out.extend(ecc128(page[j:j+128]))
        out.extend(b"\xff"*4)
    return out

def decode_card(data):
    if len(data)==69206016:
        return b"".join(data[i:i+512] for i in range(0,len(data),528))
    return data

def validate_card(data):
    if len(data)!=67108864 or not data.startswith(b"Sony PS2 Memory Card Format"):
        raise ValueError("Expected a 64 MB SD2PSX card or its PCSX2 conversion.")
    # Require the supported scene file at its verified location. Never scan the
    # whole card for TYPE strings: deleted files can retain stale car records.
    if (data[0x47a40:0x47a40+len(b"BASLUS-20189SCN")] != b"BASLUS-20189SCN" or
        int.from_bytes(data[0x47a04:0x47a08],"little") != SCENE_SIZE or
        int.from_bytes(data[0x47a10:0x47a14],"little") != 15):
        raise ValueError("Game-data file has moved or uses an unsupported layout.")
    if int.from_bytes(data[SCENE_START:SCENE_START+4],"little") != scene_checksum(data):
        raise ValueError("Game-data checksum does not match. Open an intact card backup.")
    count = int.from_bytes(data[SCENE_START+0x122:SCENE_START+0x124],"little")
    if not 1 <= count <= 50: raise ValueError("Invalid garage count (expected 1–50 cars).")
    cars = {}
    for i in range(count):
        offset = SCENE_START+0x189+i*0xA0
        raw = data[offset:offset+15].split(b"\0",1)[0].rstrip(b" ")
        if not re.fullmatch(rb"TYPE-[A-Z0-9]+",raw):
            raise ValueError(f"Car slot {i+1} has an unsupported name or record format.")
        name = raw[5:].decode("ascii")
        # Distinct tree IDs preserve duplicate models as independently editable slots.
        key = name if name not in cars else f"{name} [slot {i+1}]"
        cars[key] = offset
    return cars


def garage_groups(cars):
    result = {group: [] for group in GROUPS}
    result["Other cars"] = []
    for key in cars:
        model = key.split(" [slot ",1)[0]
        group = next((g for g,names in GROUPS.items() if model in names),"Other cars")
        result[group].append(key)
    return {g:names for g,names in result.items() if names}

SCENE_START = 0x48000
SCENE_SIZE = 8692

def scene_checksum(data):
    return sum(data[SCENE_START+4:SCENE_START+SCENE_SIZE]) & 0xffffffff

def update_checksum(data):
    data[SCENE_START:SCENE_START+4] = scene_checksum(data).to_bytes(4,"little")


def profile(data):
    return int.from_bytes(data[0x480ec:0x480f0],"little")*10, int.from_bytes(data[0x480ea:0x480ec],"little")

def write_profile(data,cash,days):
    if cash%10 or not 0<=cash<=9999990: raise ValueError("Cash must be a multiple of $10, from 0 to 9,999,990.")
    if not 0<=days<=9999: raise ValueError("Days must be between 0 and 9,999.")
    data[0x480ec:0x480f0]=(cash//10).to_bytes(4,"little")
    data[0x480ea:0x480ec]=days.to_bytes(2,"little")

class Editor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tokyo Xtreme Racer Zero • Save Editor")
        self.geometry("910x760")
        self.minsize(850,720)
        self.data=None; self.original=None; self.path=None; self.selected=None
        self.cars={}; self.pending={}; self.controls=[]; self.loading=False
        style=ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel",font=("Segoe UI",20,"bold"))
        style.configure("Heading.TLabel",font=("Segoe UI",12,"bold"))
        outer=ttk.Frame(self,padding=18); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="Tokyo Xtreme Racer Zero",style="Title.TLabel").pack(anchor="w")
        toolbar=ttk.Frame(outer); toolbar.pack(fill="x",pady=12)
        ttk.Button(toolbar,text="Open memory card…",command=self.open).pack(side="left")
        self.save_button=ttk.Button(toolbar,text="Save edited copy…",command=self.save,state="disabled")
        self.save_button.pack(side="right")
        self.status=tk.StringVar(value="Open your memory card to begin.")
        ttk.Label(outer,textvariable=self.status,wraplength=850).pack(anchor="w")
        player=ttk.LabelFrame(outer,text="Player",padding=12); player.pack(fill="x",pady=12)
        self.cash=tk.StringVar(); self.days=tk.StringVar()
        for col,(label,var) in enumerate([("Cash ($)",self.cash),("Days",self.days)]):
            ttk.Label(player,text=label).grid(row=0,column=col*2,padx=(0,8))
            entry=ttk.Entry(player,textvariable=var,width=20,state="disabled")
            entry.grid(row=0,column=col*2+1,padx=(0,24)); self.controls.append(entry)
        ttk.Label(player,text="Cash changes in $10 increments.").grid(row=1,column=0,columnspan=4,sticky="w",pady=(8,0))
        main=ttk.Frame(outer);main.pack(fill="both",expand=True)
        left=ttk.LabelFrame(main,text="Garage",padding=8);left.pack(side="left",fill="y",padx=(0,14))
        self.tree=ttk.Treeview(left,show="tree",selectmode="browse",height=21)
        self.tree.column("#0",width=220)
        scroll=ttk.Scrollbar(left,orient="vertical",command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right",fill="y")
        self.tree.pack(side="left",fill="both",expand=True)
        self.tree.bind("<<TreeviewSelect>>",self.change_car)
        right=ttk.Frame(main);right.pack(side="left",fill="both",expand=True)
        self.car_title=tk.StringVar(value="Select a car")
        ttk.Label(right,textvariable=self.car_title,style="Heading.TLabel").pack(anchor="w",pady=(0,8))
        ttk.Label(right,text="Edits stay in memory when switching cars.").pack(anchor="w",pady=(0,10))
        tabs=ttk.Notebook(right); tabs.pack(fill="both",expand=True)
        self.fields={}
        for title,parts in [("Performance",PERFORMANCE),("Aero",AERO)]:
            panel=ttk.Frame(tabs,padding=16);tabs.add(panel,text=title)
            for row,(name,offset,maximum) in enumerate(parts):
                ttk.Label(panel,text=name).grid(row=row,column=0,sticky="w",padx=(0,24),pady=7)
                var=tk.StringVar();self.fields[name]=var
                combo=ttk.Combobox(panel,textvariable=var,state="disabled",width=20,
                    values=["Stock (0)"]+[f"Level {i}" for i in range(1,maximum+1)])
                combo.grid(row=row,column=1,sticky="ew",pady=7)
                combo.bind("<<ComboboxSelected>>",self.part_changed)
                self.controls.append(combo)
            panel.columnconfigure(1,weight=1)
        ttk.Button(right,text="Reset selected car",command=self.reset_car).pack(anchor="w",pady=10)
        ttk.Label(outer,text="Checksum updates automatically. PCSX2 loading verified on the earlier save.\nSave to a separate card copy with the emulator closed. The input file is protected.",foreground="#985014",wraplength=850).pack(anchor="w",pady=(12,0))
        self.protocol("WM_DELETE_WINDOW",self.close)
    def part_changed(self,event=None):
        if self.loading or self.selected is None:return
        offset=self.cars[self.selected]
        for name,rel,_ in PARTS:
            text=self.fields[name].get()
            value=0 if text=="Stock (0)" else int(text.split()[-1])
            # Only explicitly changed fields are written, preserving unknown values.
            if value != self.data[offset+rel]:self.pending[offset+rel]=value
            else:self.pending.pop(offset+rel,None)
        self.status.set(f"{len(self.pending)} part fields changed • Save edited copy to export")
    def change_car(self,event=None):
        selection=self.tree.selection()
        if not selection or selection[0] not in self.cars:return
        self.selected=selection[0];self.loading=True
        self.car_title.set("TYPE-"+self.selected)
        base=self.cars[self.selected]
        for name,rel,_ in PARTS:
            value=self.pending.get(base+rel,self.data[base+rel])
            self.fields[name].set("Stock (0)" if value==0 else f"Level {value}")
        self.loading=False
    def reset_car(self):
        if self.selected is None:return
        base=self.cars[self.selected]
        for _,rel,_ in PARTS:self.pending.pop(base+rel,None)
        self.change_car()
        self.status.set("Selected car restored to the opened file’s values.")
    def dirty(self):
        return self.data is not None and (bool(self.pending) or
            (self.cash.get(),self.days.get())!=(f"{profile(self.data)[0]:,}",str(profile(self.data)[1])))
    def open(self):
        if self.dirty() and not messagebox.askyesno("Discard edits?","Discard unsaved edits and open another card?"):return
        path=filedialog.askopenfilename(initialdir=str(DEFAULT.parent),filetypes=[("Memory cards","*.mcd *.ps2"),("All files","*")])
        if not path:return
        try:
            data=decode_card(Path(path).read_bytes());cars=validate_card(data)
            self.data=data;self.path=Path(path);self.cars=cars;self.pending={};self.selected=None
            cash,days=profile(data);self.cash.set(f"{cash:,}");self.days.set(str(days))
            for control in self.controls:control.configure(state="readonly" if isinstance(control,ttk.Combobox) else "normal")
            self.save_button.configure(state="normal")
            self.tree.delete(*self.tree.get_children())
            for group,names in garage_groups(cars).items():
                self.tree.insert("","end",iid=group,text=group,open=True)
                for name in names:self.tree.insert(group,"end",iid=name,text="TYPE-"+name)
            self.tree.selection_set("R32RV2" if "R32RV2" in cars else next(iter(cars)));self.change_car()
            self.status.set(f"Loaded {self.path.name} • {len(cars)} cars • checksum verified")
        except Exception as exc:messagebox.showerror("Cannot open card",str(exc))
    def save(self):
        if self.data is None:return
        try:
            edited=bytearray(self.data)
            write_profile(edited,int(self.cash.get().replace(",","")),int(self.days.get().replace(",","")))
            for offset,value in self.pending.items():edited[offset]=value
            out=filedialog.asksaveasfilename(
                title="Save edited memory card copy",
                defaultextension=".ps2",
                initialfile=self.path.stem+"-edited",
                filetypes=[("PCSX2 memory card (*.ps2)","*.ps2"),
                           ("SD2PSX memory card (*.mcd)","*.mcd")])
            if not out:return
            target=Path(out)
            if target.resolve()==self.path.resolve() or (target.exists() and target.samefile(self.path)):
                raise ValueError("Choose a separate output file; the input card is protected.")
            if target.suffix.lower() not in (".ps2",".mcd"):
                raise ValueError("Choose .ps2 for PCSX2 or .mcd for SD2PSX.")
            update_checksum(edited)
            self.status.set("Preparing card copy…")
            self.update_idletasks()
            target.write_bytes(encode_ps2(edited) if target.suffix.lower()==".ps2" else edited)
            self.status.set(f"Saved {target.name} • experimental copy; input unchanged")
            messagebox.showinfo("Copy saved","Edited copy saved. Checksum updated; in-game loading still needs verification.")
        except Exception as exc:messagebox.showerror("Cannot save",str(exc))
    def close(self):
        if self.dirty() and not messagebox.askyesno("Close editor?","Close and discard the edits held in memory?"):return
        self.destroy()
if __name__=="__main__":Editor().mainloop()

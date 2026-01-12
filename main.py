#!/usr/bin/env python3
import customtkinter as ctk
import speech_recognition as sr
import threading, os, sys, math, platform, re, asyncio, tempfile

try: import psutil
except: psutil = None

try:
    import edge_tts, pygame
    pygame.mixer.init()
    USE_EDGE_TTS = True
except: USE_EDGE_TTS = False

from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("need api key in .env file")
    sys.exit(1)

rec = sr.Recognizer()
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
IS_WINDOWS = platform.system() == "Windows"
MIC_INDEX = 2 if IS_WINDOWS else None
chat_log = []

def strip_md(t):
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
    t = re.sub(r'\*(.+?)\*', r'\1', t)
    t = re.sub(r'__(.+?)__', r'\1', t)
    t = re.sub(r'_(.+?)_', r'\1', t)
    t = re.sub(r'(.+?)', r'\1', t)
    t = re.sub(r'#{1,6}\s*', '', t)
    t = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', t)
    t = re.sub(r'^\s*[-*+]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)
    return t.strip()

def parse_md(txt):
    parts = []
    pat = r'``(\w*)\n?(.*?)``'
    last = 0
    for m in re.finditer(pat, txt, re.DOTALL):
        if m.start() > last: parts.append(('txt', txt[last:m.start()]))
        parts.append(('code', m.group(2).strip(), m.group(1) or 'code'))
        last = m.end()
    if last < len(txt): parts.append(('txt', txt[last:]))
    return parts if parts else [('txt', txt)]

def fmt_txt(t):
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)
    t = re.sub(r'__(.+?)__', r'\1', t)
    t = re.sub(r'\*(.+?)\*', r'\1', t)
    t = re.sub(r'_(.+?)_', r'\1', t)
    t = re.sub(r'`(.+?)`', r'\1', t)
    t = re.sub(r'#{1,6}\s*(.+)', r'\1', t)
    t = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', t)
    return t.strip()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("1280x720+0+0")
        self.configure(fg_color="#000")
        self.title("Oracle")
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        
        self.listening = False
        self.phase = 0.0
        self.showing_hist = False
        self.stream_txt = ""
        self.speaking = False
        self.loading = False
        
        self.main_fr = ctk.CTkFrame(self, fg_color="#000")
        self.main_fr.pack(fill="both", expand=True)
        
        self.orb_fr = ctk.CTkFrame(self.main_fr, fg_color="#000")
        self.orb_fr.pack(fill="both", expand=True)
        
        top = ctk.CTkFrame(self.orb_fr, fg_color="#000", height=50)
        top.pack(fill="x", pady=10)
        top.pack_propagate(False)
        
        self.batt = ctk.CTkLabel(top, text="--", font=("Arial", 14), text_color="#555")
        self.batt.pack(side="left", padx=20)
        
        self.hist_btn = ctk.CTkButton(top, text="History", width=80, height=32,
            fg_color="#1a1a1a", hover_color="#333", border_width=1, border_color="#0aa",
            font=("Arial", 13), command=self.toggle_hist)
        self.hist_btn.pack(side="right", padx=20)
        
        self.canv = ctk.CTkCanvas(self.orb_fr, width=1280, height=350, bg="black", highlightthickness=0)
        self.canv.pack(pady=10)
        self.orb = self.canv.create_oval(0,0,0,0, outline="#0ff", width=5)
        
        self.stat = ctk.CTkLabel(self.orb_fr, text="Tap to speak", font=("Arial", 18, "bold"), 
            text_color="#666", wraplength=650)
        self.stat.pack(pady=20, padx=30)
        
        self.hist_fr = ctk.CTkFrame(self.main_fr, fg_color="#0a0a0a")
        
        htop = ctk.CTkFrame(self.hist_fr, fg_color="#111", height=55)
        htop.pack(fill="x")
        htop.pack_propagate(False)
        ctk.CTkLabel(htop, text="Chat History", font=("Arial", 18, "bold"), text_color="#0dd").pack(side="left", padx=20, pady=14)
        ctk.CTkButton(htop, text="Back", width=70, height=34, fg_color="#333", hover_color="#444",
            font=("Arial", 13), command=self.toggle_hist).pack(side="right", padx=20, pady=10)
        
        self.hist_scroll = ctk.CTkScrollableFrame(self.hist_fr, fg_color="#0a0a0a")
        self.hist_scroll.pack(fill="both", expand=True, padx=15, pady=10)
        
        hbot = ctk.CTkFrame(self.hist_fr, fg_color="#111", height=60)
        hbot.pack(fill="x", side="bottom")
        hbot.pack_propagate(False)
        ctk.CTkButton(hbot, text="Exit to Desktop", width=150, height=42, fg_color="#900", hover_color="#b00",
            font=("Arial", 14, "bold"), command=self.quit_app).pack(pady=9)
        
        self.canv.bind("<Button-1>", self.on_tap)
        self.bind("<space>", self.on_tap)
        self.bind("<Escape>", lambda e: self.quit_app())
        
        self.upd_batt()
        self.anim()
    
    def toggle_hist(self):
        if self.showing_hist:
            self.hist_fr.pack_forget()
            self.orb_fr.pack(fill="both", expand=True)
            self.showing_hist = False
        else:
            self.orb_fr.pack_forget()
            self.refresh_hist()
            self.hist_fr.pack(fill="both", expand=True)
            self.showing_hist = True
    
    def refresh_hist(self):
        for w in self.hist_scroll.winfo_children(): w.destroy()
        
        if not chat_log:
            ctk.CTkLabel(self.hist_scroll, text="", height=200).pack()
            ctk.CTkLabel(self.hist_scroll, text="No messages yet", font=("Arial", 20), text_color="#444").pack()
            ctk.CTkLabel(self.hist_scroll, text="tap the orb to talk", font=("Arial", 14), text_color="#333").pack(pady=8)
        else:
            for who, txt in chat_log:
                row = ctk.CTkFrame(self.hist_scroll, fg_color="transparent")
                row.pack(fill="x", pady=6)
                if who == "user":
                    bub = ctk.CTkFrame(row, fg_color="#0055aa", corner_radius=14)
                    bub.pack(anchor="e", padx=(100, 10))
                    nc, nm = "#8cf", "You"
                else:
                    bub = ctk.CTkFrame(row, fg_color="#1a1a1a", corner_radius=14)
                    bub.pack(anchor="w", padx=(10, 100))
                    nc, nm = "#0ff", "Oracle"
                
                ctk.CTkLabel(bub, text=nm, font=("Arial", 11, "bold"), text_color=nc).pack(anchor="w", padx=14, pady=(10,2))
                for p in parse_md(txt):
                    if p[0] == 'code':
                        cf = ctk.CTkFrame(bub, fg_color="#222", corner_radius=8)
                        cf.pack(anchor="w", padx=10, pady=4, fill="x")
                        if len(p) > 2 and p[2]:
                            ctk.CTkLabel(cf, text=p[2], font=("Consolas", 10), text_color="#888").pack(anchor="w", padx=8, pady=(6,0))
                        ctk.CTkLabel(cf, text=p[1], font=("Consolas", 12), text_color="#0f0", wraplength=450, justify="left").pack(anchor="w", padx=8, pady=(4,8))
                    else:
                        f = fmt_txt(p[1])
                        if f.strip():
                            ctk.CTkLabel(bub, text=f, font=("Arial", 13), text_color="#fff", wraplength=500, justify="left").pack(anchor="w", padx=14, pady=(2,2))
                ctk.CTkLabel(bub, text="", height=6).pack()
            self.after(100, lambda: self.hist_scroll._parent_canvas.yview_moveto(1.0))
    
    def quit_app(self):
        self.destroy()
        sys.exit(0)
    
    def upd_batt(self):
        try:
            if psutil:
                b = psutil.sensors_battery()
                if b:
                    ch = "+" if b.power_plugged else ""
                    self.batt.configure(text=f"{ch}{int(b.percent)}%")
        except: pass
        self.after(30000, self.upd_batt)
    
    def anim(self):
        self.phase += 0.15
        p = math.sin(self.phase) * 12
        cx, cy = 640, 175
        
        if self.loading:
            col, r = "#ffaa00", 70 + math.sin(self.phase * 0.8) * 15
        elif self.speaking:
            col, r = "#00ff88", 75 + p * 1.5
        elif self.listening:
            col, r = "#ff3333", 80 + p * 2
        else:
            col, r = "#00ffff", 65 + p
        
        self.canv.coords(self.orb, cx-r, cy-r, cx+r, cy+r)
        self.canv.itemconfig(self.orb, outline=col, width=5)
        self.after(30, self.anim)
    
    def set_stat(self, t):
        self.stat.configure(text=strip_md(t))
        self.update()
    
    def on_tap(self, e=None):
        if self.showing_hist: return
        if self.speaking:
            self.stop_speak()
            return
        if self.listening: return
        self.listening = True
        threading.Thread(target=self.listen_respond, daemon=True).start()
    
    def stop_speak(self):
        self.speaking = False
        if USE_EDGE_TTS:
            try: pygame.mixer.music.stop()
            except: pass
        self.set_stat("Tap to speak")
    
    def listen_respond(self):
        global chat_log
        self.set_stat("Listening...")
        
        try:
            mic = sr.Microphone(device_index=MIC_INDEX)
            with mic as src:
                rec.energy_threshold = 150
                rec.dynamic_energy_threshold = True
                rec.adjust_for_ambient_noise(src, duration=0.6)
                audio = rec.listen(src, timeout=12, phrase_time_limit=18)
            
            self.listening = False
            self.loading = True
            self.set_stat("Thinking...")
            txt = rec.recognize_google(audio)
            print(f"heard: {txt}")
            chat_log.append(("user", txt))
            
            self.stream_txt = ""
            stream = client.chat.completions.create(
                model="allenai/molmo-2-8b:free",
                messages=[
                    {"role": "system", "content": "You are Oracle. Answer in 1-2 short sentences."},
                    {"role": "user", "content": txt}
                ],
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    self.stream_txt += chunk.choices[0].delta.content
                    self.set_stat(self.stream_txt)
            
            reply = self.stream_txt
            print(f"oracle: {reply}")
            chat_log.append(("ai", reply))
            self.speak(strip_md(reply))
            
        except sr.WaitTimeoutError:
            self.set_stat("didnt hear anything")
        except sr.UnknownValueError:
            self.set_stat("couldnt understand")
            self.speak("sorry, didnt catch that")
        except Exception as e:
            print(f"err: {e}")
            self.set_stat("error :(")
        
        self.listening = False
        self.loading = False
        self.set_stat("Tap to speak")
    
    def speak(self, txt):
        self.loading = False
        self.speaking = True
        try:
            if USE_EDGE_TTS:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                tmp.close()
                async def gen():
                    c = edge_tts.Communicate(txt, "en-US-AriaNeural")
                    await c.save(tmp.name)
                asyncio.run(gen())
                pygame.mixer.music.load(tmp.name)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and self.speaking:
                    pygame.time.wait(100)
                pygame.mixer.music.stop()
                try: os.unlink(tmp.name)
                except: pass
            else:
                print("edge-tts not available")
        except Exception as e:
            print(f"tts err: {e}")
        self.speaking = False

if __name__ == "__main__":
    app = App()
    app.mainloop()

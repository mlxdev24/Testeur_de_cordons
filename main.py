import json
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import serial
from serial.tools import list_ports

# Configuration du thème CustomTkinter
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class CableTesterGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Cable Tester - UART -> JSON")
        self.geometry("900x750")
        self.resizable(True, True)
        self.minsize(850, 700)

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="38400")
        self.timeout_var = tk.StringVar(value="2.0")
        self.cmd_var = tk.StringVar(value="TEST\\n")  # tu peux mettre "TEST" si besoin

        # Références JSON chargées: {nom_fichier: données_json}
        self.references = {}
        self.active_reference = None  # Nom du fichier actif

        # État d'identification du testeur
        self.tester_identified = False

        # Connexion série unique (gardée ouverte)
        self.serial_port = None

        # Dossier Références
        self.references_dir = os.path.join(os.getcwd(), "Références")

        self._build_ui()
        self.refresh_ports()
        self._create_references_directory()
        self._center_window()

        # Fermeture propre du port série à la fermeture de l'app
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _center_window(self):
        """Centre la fenêtre sur l'écran"""
        self.update_idletasks()

        # Obtenir les dimensions de l'écran
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Obtenir les dimensions de la fenêtre
        window_width = self.winfo_width()
        window_height = self.winfo_height()

        # Calculer la position centrale
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)

        # Positionner la fenêtre
        self.geometry(f"+{x}+{y}")

    def _create_references_directory(self):
        """Crée le dossier Références s'il n'existe pas"""
        try:
            if not os.path.exists(self.references_dir):
                os.makedirs(self.references_dir)
                self.log_line(f"✓ Dossier 'Références' créé : {self.references_dir}")
            else:
                self.log_line(f"✓ Dossier 'Références' disponible : {self.references_dir}")
        except Exception as e:
            self.log_line(f"✗ Erreur lors de la création du dossier Références : {e}")

    def _build_ui(self):
        pad = 15

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="both", expand=True, padx=pad, pady=pad)

        # ===== SECTION CONFIGURATION UART =====
        uart_frame = ctk.CTkFrame(frm, corner_radius=10)
        uart_frame.pack(fill="x", pady=(0, 10), padx=5)

        uart_label = ctk.CTkLabel(uart_frame, text="Configuration UART", font=("", 14, "bold"))
        uart_label.pack(pady=(10, 5), padx=10, anchor="w")

        # Ligne 1: Port
        port_row = ctk.CTkFrame(uart_frame, fg_color="transparent")
        port_row.pack(fill="x", pady=(0, 8), padx=10)

        ctk.CTkLabel(port_row, text="Port :", font=("", 12, "bold"), width=80).pack(side="left", padx=(0, 5))
        self.port_combo = ctk.CTkComboBox(port_row, variable=self.port_var, state="readonly", width=250, font=("", 11))
        self.port_combo.pack(side="left", padx=(0, 10))
        ctk.CTkButton(port_row, text="🔄 Re-scanner", command=self.refresh_ports, width=100).pack(side="left", padx=(0, 10))
        self.identify_btn = ctk.CTkButton(port_row, text="🔌 Connecter", command=self.identify_tester, width=120)
        self.identify_btn.pack(side="left", padx=(0, 5))
        self.disconnect_btn = ctk.CTkButton(port_row, text="❌ Déconnecter", command=self.disconnect_tester, width=120, state="disabled")
        self.disconnect_btn.pack(side="left")

        # Ligne 2: Paramètres
        params_row = ctk.CTkFrame(uart_frame, fg_color="transparent")
        params_row.pack(fill="x", pady=(0, 10), padx=10)

        ctk.CTkLabel(params_row, text="Baudrate :", font=("", 12, "bold"), width=80).pack(side="left", padx=(0, 5))
        ctk.CTkEntry(params_row, textvariable=self.baud_var, width=120, font=("", 11)).pack(side="left", padx=(0, 30))

        ctk.CTkLabel(params_row, text="Timeout :", font=("", 12, "bold")).pack(side="left", padx=(0, 5))
        ctk.CTkEntry(params_row, textvariable=self.timeout_var, width=80, font=("", 11)).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(params_row, text="secondes", font=("", 10)).pack(side="left")

        # ===== SECTION RÉFÉRENCE =====
        ref_frame = ctk.CTkFrame(frm, corner_radius=10)
        ref_frame.pack(fill="x", pady=(0, 10), padx=5)

        ref_label = ctk.CTkLabel(ref_frame, text="Référence de câblage", font=("", 14, "bold"))
        ref_label.pack(pady=(10, 5), padx=10, anchor="w")

        # Champ référence
        ref_display = ctk.CTkFrame(ref_frame, fg_color="transparent")
        ref_display.pack(fill="x", pady=(0, 8), padx=10)

        self.active_ref_var = tk.StringVar(value="Aucune référence chargée")
        ref_entry = ctk.CTkEntry(ref_display, textvariable=self.active_ref_var, state="readonly", font=("", 11, "bold"))
        ref_entry.pack(fill="x")

        # Boutons gestion référence
        ref_buttons = ctk.CTkFrame(ref_frame, fg_color="transparent")
        ref_buttons.pack(fill="x", pady=(0, 10), padx=10)

        ctk.CTkButton(ref_buttons, text="📁 Charger une référence", command=self.load_reference, width=200).pack(side="left", padx=(0, 8))
        ctk.CTkButton(ref_buttons, text="🗑️ Effacer", command=self.clear_reference, width=120).pack(side="left")

        # ===== SECTION ACTIONS =====
        action_frame = ctk.CTkFrame(frm, corner_radius=10)
        action_frame.pack(fill="x", pady=(0, 10), padx=5)

        action_label = ctk.CTkLabel(action_frame, text="Actions", font=("", 14, "bold"))
        action_label.pack(pady=(10, 5), padx=10, anchor="w")

        action_buttons = ctk.CTkFrame(action_frame, fg_color="transparent")
        action_buttons.pack(pady=(0, 10), padx=10)

        self.save_btn = ctk.CTkButton(action_buttons, text="💾 Enregistrer un nouveau câble",
                                    command=self.on_save_clicked, width=250, height=35, font=("", 12),
                                    state="disabled")
        self.save_btn.pack(side="left", padx=(0, 15))

        self.test_btn = ctk.CTkButton(action_buttons, text="✓ Tester la conformité",
                                    command=self.on_test_clicked, width=250, height=35, font=("", 12),
                                    state="disabled")
        self.test_btn.pack(side="left")

        # ===== STATUS BAR =====
        status_frame = ctk.CTkFrame(frm, fg_color="transparent")
        status_frame.pack(fill="x", pady=(0, 8), padx=5)

        ctk.CTkLabel(status_frame, text="État :", font=("", 11, "bold")).pack(side="left", padx=(0, 5))
        self.status_var = tk.StringVar(value="Prêt.")
        self.status_label = ctk.CTkLabel(status_frame, textvariable=self.status_var, font=("", 11), text_color="#0066cc")
        self.status_label.pack(side="left")

        # ===== LOG =====
        log_frame = ctk.CTkFrame(frm, corner_radius=10)
        log_frame.pack(fill="both", expand=True, padx=5)

        log_label = ctk.CTkLabel(log_frame, text="📋 Journal d'activité", font=("", 14, "bold"))
        log_label.pack(pady=(10, 5), padx=10, anchor="w")

        # Scrollbar pour les logs
        log_container = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        log_scroll = tk.Scrollbar(log_container)
        log_scroll.pack(side="right", fill="y")

        self.log = tk.Text(log_container, height=14, wrap="word", font=("Courier", 10),
                          yscrollcommand=log_scroll.set, bg="#2b2b2b", fg="#ffffff",
                          insertbackground="#ffffff", relief="flat")
        self.log.pack(side="left", fill="both", expand=True)
        log_scroll.config(command=self.log.yview)
        self.log.configure(state="disabled")

    def log_line(self, s: str):
        self.log.configure(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_status(self, s: str):
        self.status_var.set(s)

    def refresh_ports(self):
        # Déconnexion du port actuel si nécessaire
        if self.serial_port is not None:
            self.disconnect_tester()

        ports = list(list_ports.comports())
        items = [p.device for p in ports]

        # Réinitialisation de l'identification lors du changement de ports
        self.tester_identified = False
        self.save_btn.configure(state="disabled")
        self.test_btn.configure(state="disabled")

        self.port_combo.configure(values=items)
        if items:
            # garde sélection si possible
            current = self.port_var.get()
            if current not in items:
                self.port_var.set(items[0])
            self.set_status(f"{len(items)} port(s) détecté(s). Identification requise.")
        else:
            self.port_var.set("")
            self.set_status("Aucun port détecté.")

        self.log_line("Ports détectés : " + (", ".join(items) if items else "(aucun)"))

        # Détection automatique du testeur de câbles TTL-232R-5V-WE
        self._auto_detect_tester(ports)

    def _auto_detect_tester(self, ports):
        """Détecte automatiquement le testeur TTL-232R-5V-WE et propose de se connecter"""
        # Recherche du périphérique spécifique
        # VID: 0x0403 (FTDI), PID: 0x6001
        target_vid = 0x0403
        target_pid = 0x6001

        for port_info in ports:
            # Vérification VID/PID
            if port_info.vid == target_vid and port_info.pid == target_pid:
                # Périphérique trouvé
                device_name = port_info.device
                description = port_info.description if port_info.description else "Inconnu"

                self.log_line(f"✓ Testeur de câbles détecté : {description} sur {device_name}")

                # Proposer la connexion automatique
                response = messagebox.askyesno(
                    "Testeur de câbles détecté",
                    f"Un testeur de câbles a été détecté :\n\n"
                    f"Port : {device_name}\n"
                    f"Périphérique : {description}\n"
                    f"VID:PID : {port_info.vid:04X}:{port_info.pid:04X}\n\n"
                    f"Voulez-vous vous connecter automatiquement ?"
                )

                if response:
                    # Sélectionner le port
                    self.port_var.set(device_name)
                    self.log_line(f"Connexion automatique au testeur sur {device_name}...")

                    # Lancer la connexion après un court délai pour que l'interface se mette à jour
                    self.after(100, self.identify_tester)

                break  # Un seul testeur à la fois

    def identify_tester(self):
        """Identifie le testeur en envoyant une commande d'identification"""
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Port manquant", "Sélectionne un port UART avant d'identifier le testeur.")
            return

        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            messagebox.showwarning("Baudrate invalide", "Entre un baudrate valide (ex: 38400).")
            return

        self.log_line(f"Tentative d'identification du testeur sur {port}...")
        self.identify_btn.configure(state="disabled")
        self.set_status("Identification en cours…")

        # Thread pour l'identification
        th = threading.Thread(
            target=self._worker_identify,
            args=(port, baud),
            daemon=True,
        )
        th.start()

    def disconnect_tester(self):
        """Déconnecte le testeur et ferme le port série"""
        if self.serial_port is not None:
            try:
                self.serial_port.close()
                self.log_line(f"✓ Déconnexion du port {self.serial_port.port}")
            except Exception as e:
                self.log_line(f"✗ Erreur lors de la déconnexion : {e}")
            finally:
                self.serial_port = None

        # Réinitialisation de l'état
        self.tester_identified = False
        self.save_btn.configure(state="disabled")
        self.test_btn.configure(state="disabled")
        self.identify_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")
        self.set_status("Déconnecté.")

    def _worker_identify(self, port, baud):
        """Worker thread pour l'identification du testeur - OUVRE LE PORT ET LE GARDE OUVERT"""
        try:
            # Commande d'identification
            id_cmd = b"IDN\n"
            timeout = 0.2

            # Ouverture du port série (SANS with, pour le garder ouvert)
            ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)

            # Flush des buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.1)

            # Envoi de la commande d'identification
            ser.write(id_cmd)
            ser.flush()

            # Lecture de TOUTE la réponse jusqu'à ce qu'il n'y ait plus rien
            response_bytes = b""
            start_time = time.time()
            max_wait = 2.0

            while time.time() - start_time < max_wait:
                chunk = ser.read(1024)
                if chunk:
                    response_bytes += chunk
                else:
                    # Si rien reçu, attendre un peu et réessayer
                    if len(response_bytes) > 0:
                        # On a déjà reçu quelque chose, attendre un peu pour voir si plus de données arrivent
                        time.sleep(0.1)
                        final_chunk = ser.read(1024)
                        if final_chunk:
                            response_bytes += final_chunk
                        else:
                            break  # Plus rien à lire
                    else:
                        time.sleep(0.05)

            response = response_bytes.decode("utf-8", errors="ignore").strip()

            # Vérification de la réponse (doit contenir "Testeur de cordon")
            if "Testeur de cordon" in response:
                # SUCCÈS : on garde le port ouvert
                self.after(0, lambda s=ser, r=response: self._finish_identify(True, r, s))
            else:
                # ÉCHEC : on ferme le port
                ser.close()
                error_msg = f"Réponse invalide : '{response}'" if response else "Aucune réponse"
                self.after(0, lambda e=error_msg: self._finish_identify(False, e, None))

        except Exception as e:
            # En cas d'erreur, fermer le port si ouvert
            if 'ser' in locals() and ser is not None:
                try:
                    ser.close()
                except:
                    pass
            self.after(0, lambda: self._finish_identify(False, str(e), None))

    def _finish_identify(self, success, response, serial_obj):
        """Traite le résultat de l'identification"""
        self.identify_btn.configure(state="normal")

        if success:
            # Stocker le port série pour réutilisation
            self.serial_port = serial_obj

            self.tester_identified = True
            self.save_btn.configure(state="normal")
            self.test_btn.configure(state="normal")
            self.identify_btn.configure(state="disabled")
            self.disconnect_btn.configure(state="normal")
            self.set_status("✓ Testeur connecté et prêt")
            self.log_line(f"✓ Testeur identifié : {response}")
            self.log_line(f"✓ Port {self.serial_port.port} maintenu ouvert pour les opérations suivantes")
            messagebox.showinfo("Connexion réussie", f"Le testeur est connecté et prêt.\n\nRéponse : {response}\n\nLe port restera ouvert jusqu'à la déconnexion.")
        else:
            self.tester_identified = False
            self.serial_port = None
            self.save_btn.configure(state="disabled")
            self.test_btn.configure(state="disabled")
            self.disconnect_btn.configure(state="disabled")
            self.set_status("✗ Échec de connexion")
            self.log_line(f"✗ Échec d'identification : {response}")
            messagebox.showerror("Échec de connexion",
                               f"Le testeur n'a pas pu être identifié.\n\nErreur : {response}\n\nVérifiez :\n- Le port est correct\n- Le testeur est allumé\n- Le baudrate est correct")

    def check_port_available(self, port, baud):
        """Vérifie si le port UART est disponible et accessible"""
        try:
            # Essai d'ouverture rapide du port
            with serial.Serial(port=port, baudrate=baud, timeout=0.1) as ser:
                # Flush des buffers pour nettoyer
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                time.sleep(0.05)  # Petit délai pour laisser le buffer se vider
            return True, None
        except serial.SerialException as e:
            error_msg = str(e)
            if "Permission denied" in error_msg or "Access is denied" in error_msg:
                return False, "Permission refusée. Vérifiez les droits d'accès au port."
            elif "could not open port" in error_msg.lower() or "cannot open" in error_msg.lower():
                return False, f"Impossible d'ouvrir le port {port}. Il est peut-être déjà utilisé par une autre application."
            else:
                return False, f"Erreur d'accès au port: {error_msg}"
        except Exception as e:
            return False, f"Erreur inattendue: {str(e)}"

    def load_reference(self):
        """Charge un fichier JSON de référence"""
        self.set_status("Ouverture du sélecteur de fichiers...")
        self.update_idletasks()  # Force la mise à jour de l'interface

        filepath = filedialog.askopenfilename(
            title="Charger une référence JSON",
            initialdir=self.references_dir,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Tous les fichiers", "*.*")],
        )

        if not filepath:
            self.set_status("Prêt.")
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Vérification que c'est un dictionnaire
            if not isinstance(data, dict):
                messagebox.showerror("Erreur", "Le fichier JSON doit contenir un objet/dictionnaire.")
                return

            # Nom affiché = nom du fichier
            filename = os.path.basename(filepath)

            # Sauvegarde de la référence
            self.references[filename] = {"path": filepath, "data": data}
            self.active_reference = filename
            self.update_reference_display()

            self.log_line(f"Référence chargée : {filename}")
            self.set_status("Prêt.")

        except json.JSONDecodeError as e:
            self.set_status("Erreur de chargement.")
            messagebox.showerror("Erreur JSON", f"Impossible de lire le fichier JSON:\n{e}")
        except Exception as e:
            self.set_status("Erreur de chargement.")
            messagebox.showerror("Erreur", f"Erreur lors du chargement:\n{e}")

    def clear_reference(self):
        """Efface la référence active"""
        if not self.active_reference:
            messagebox.showinfo("Aucune référence", "Il n'y a pas de référence active à effacer.")
            return

        filename = self.active_reference
        filepath = self.references[filename]["path"]

        # Popup personnalisée avec checkbox
        result = self._show_confirm_dialog(
            "Confirmer l'effacement",
            f"Effacer la référence '{filename}' ?\n\n{filepath}",
            "Supprimer aussi le fichier physique (⚠️ irréversible)"
        )

        if result is None:  # Annulé
            return

        confirm, delete_file = result

        # Suppression du fichier si demandé
        if delete_file:
            try:
                os.remove(filepath)
                self.log_line(f"✓ Fichier supprimé : {filepath}")
            except Exception as e:
                self.log_line(f"✗ Erreur lors de la suppression du fichier : {e}")
                messagebox.showerror("Erreur", f"Impossible de supprimer le fichier :\n{e}")

        # Effacement de la référence active
        self.active_reference = None
        if filename in self.references:
            del self.references[filename]

        self.update_reference_display()
        self.log_line(f"Référence effacée : {filename}")

    def update_reference_display(self):
        """Met à jour l'affichage de la référence active"""
        if self.active_reference and self.active_reference in self.references:
            ref_data = self.references[self.active_reference]
            num_pins = len(ref_data["data"])
            filepath = ref_data["path"]
            parent_dir = os.path.basename(os.path.dirname(filepath))
            self.active_ref_var.set(f"{parent_dir}/{self.active_reference} ({num_pins} pins)")
        else:
            self.active_ref_var.set("Aucune référence chargée")

    def _show_confirm_dialog(self, title, message, checkbox_text, default_checked=False):
        """Affiche une popup de confirmation avec une case à cocher

        Returns:
            tuple: (confirmed, checkbox_value) ou None si annulé
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("500x220")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Centrage
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        result = {"confirmed": False, "checkbox": False}

        # Message
        msg_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        msg_frame.pack(fill="both", expand=True, padx=15, pady=15)

        msg_label = ctk.CTkLabel(msg_frame, text=message, font=("", 11), justify="left")
        msg_label.pack(pady=(0, 15))

        # Checkbox
        checkbox_var = tk.BooleanVar(value=default_checked)
        checkbox = ctk.CTkCheckBox(msg_frame, text=checkbox_text, variable=checkbox_var, font=("", 11))
        checkbox.pack(anchor="w", pady=(0, 10))

        # Boutons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        def on_ok():
            result["confirmed"] = True
            result["checkbox"] = checkbox_var.get()
            dialog.destroy()

        def on_cancel():
            result["confirmed"] = False
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="OK", command=on_ok, width=100).pack(side="right", padx=(5, 0))
        ctk.CTkButton(btn_frame, text="Annuler", command=on_cancel, width=100).pack(side="right")

        # Attendre la fermeture
        dialog.wait_window()

        if result["confirmed"]:
            return (True, result["checkbox"])
        return None

    def on_test_clicked(self):
        """Lance un test de conformité avec la référence active"""
        # Vérification que le testeur est identifié
        if not self.tester_identified:
            messagebox.showwarning("Testeur non identifié", "Identifie d'abord le testeur avec le bouton '🔌 Identifier'.")
            return

        # Vérification qu'une référence est active
        if not self.active_reference or self.active_reference not in self.references:
            messagebox.showwarning("Référence manquante", "Charge ou sélectionne une référence active avant de tester.")
            return

        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Port manquant", "Sélectionne un port UART.")
            return

        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            messagebox.showwarning("Baudrate invalide", "Entre un baudrate valide (ex: 115200).")
            return

        try:
            timeout = float(self.timeout_var.get().strip())
        except ValueError:
            messagebox.showwarning("Timeout invalide", "Entre un timeout valide (ex: 2.0).")
            return

        cmd_text = self.cmd_var.get()
        cmd_bytes = cmd_text.encode("utf-8").decode("unicode_escape").encode("utf-8")

        # Désactivation des boutons pendant le test
        self.test_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.set_status("Test en cours…")
        self.log_line(f"Test de conformité avec {self.active_reference}…")
        self.log_line(f"Ouverture {port} @ {baud}… envoi commande: {cmd_text!r}")

        # Récupération de la référence
        ref_data = self.references[self.active_reference]["data"]

        th = threading.Thread(
            target=self._worker_test,
            args=(port, baud, timeout, cmd_bytes, ref_data),
            daemon=True,
        )
        th.start()

    def _worker_test(self, port, baud, timeout, cmd_bytes, ref_data):
        """Worker thread pour effectuer le test de conformité"""
        try:
            data = self._run_test_get_json(port, baud, timeout, cmd_bytes)
            # Comparaison
            is_conform = self._compare_json(ref_data, data)
            self.after(0, lambda: self._finish_test(is_conform, data))
        except Exception as e:
            print(e)
            self.after(0, lambda: self._finish_test_err(str(e)))

    def _compare_json(self, ref_data, test_data):
        """Compare deux dictionnaires JSON"""
        return ref_data == test_data

    def _finish_test(self, is_conform, data):
        """Affiche le résultat du test"""
        self.set_status("Test terminé.")
        self.test_btn.configure(state="normal")
        self.save_btn.configure(state="normal")

        if is_conform:
            self.log_line("✓ Test CONFORME : les données correspondent à la référence.")
            self._show_result_popup("CONFORME", "#28a745", "white")  # Vert
        else:
            self.log_line("✗ Test NON-CONFORME : les données diffèrent de la référence.")
            self.log_line(f"Données reçues : {json.dumps(data, ensure_ascii=False)[:200]}...")
            self._show_result_popup("NON-CONFORME", "#dc3545", "white")  # Rouge

    def _finish_test_err(self, msg):
        """Gère les erreurs lors du test"""
        self.log_line("ERREUR lors du test: " + msg)
        self.set_status("Erreur.")
        self.test_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        messagebox.showerror("Erreur de test", msg)

    def _show_result_popup(self, text, bg_color, fg_color):
        """Affiche une popup colorée avec le résultat"""
        popup = ctk.CTkToplevel(self)
        popup.title("Résultat du test")
        popup.geometry("600x300")
        popup.resizable(False, False)

        # Centrer la popup sur la fenêtre principale
        popup.transient(self)
        popup.grab_set()

        # Position centrée sur la fenêtre parent
        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

        # Frame principal avec couleur de fond
        main_frame = ctk.CTkFrame(popup, fg_color=bg_color, corner_radius=0)
        main_frame.pack(fill="both", expand=True)

        # Label avec le texte
        label = ctk.CTkLabel(
            main_frame,
            text=text,
            font=("Arial", 40, "bold"),
            text_color=fg_color
        )
        label.pack(expand=True, pady=30)

        # Bouton OK
        btn = ctk.CTkButton(
            main_frame,
            text="OK",
            command=popup.destroy,
            font=("Arial", 14),
            width=150,
            height=45,
            fg_color=fg_color,
            text_color=bg_color,
            hover_color="#e0e0e0"
        )
        btn.pack(pady=(0, 30))

        # Fermeture automatique après 3 secondes
        popup.after(3000, popup.destroy)

    def on_save_clicked(self):
        # Vérification que le testeur est identifié
        if not self.tester_identified:
            messagebox.showwarning("Testeur non identifié", "Identifie d'abord le testeur avec le bouton '🔌 Identifier'.")
            return

        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Port manquant", "Sélectionne un port UART.")
            return

        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            messagebox.showwarning("Baudrate invalide", "Entre un baudrate valide (ex: 115200).")
            return

        try:
            timeout = float(self.timeout_var.get().strip())
        except ValueError:
            messagebox.showwarning("Timeout invalide", "Entre un timeout valide (ex: 2.0).")
            return

        cmd_text = self.cmd_var.get()
        cmd_bytes = cmd_text.encode("utf-8").decode("unicode_escape").encode("utf-8")
        # (permet d'écrire TEST\n dans le champ)

        # Choix du fichier de sortie (avant de lancer le test)
        filepath = filedialog.asksaveasfilename(
            title="Enregistrer le brochage",
            initialdir=self.references_dir,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Tous les fichiers", "*.*")],
        )
        if not filepath:
            return

        self.save_btn.configure(state="disabled")
        self.set_status("Test en cours…")
        self.log_line(f"Ouverture {port} @ {baud}… envoi commande: {cmd_text!r}")

        th = threading.Thread(
            target=self._worker_test_and_save,
            args=(port, baud, timeout, cmd_bytes, filepath),
            daemon=True,
        )
        th.start()

    def _worker_test_and_save(self, port, baud, timeout, cmd_bytes, filepath):
        try:
            data = self._run_test_get_json(port, baud, timeout, cmd_bytes)
            # Sauvegarde JSON pretty
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.after(0, lambda: self._finish_ok(filepath, data))
        except Exception as e:
            print(e)
            self.after(0, lambda: self._finish_err(str(e)))

    def _finish_ok(self, filepath, data):
        self.log_line(f"JSON reçu OK. Sauvegardé : {filepath}")
        self.log_line(f"Contenu (aperçu): {json.dumps(data, ensure_ascii=False)[:200]}...")
        self.set_status("Enregistrement terminé.")
        self.save_btn.configure(state="normal")

        # Popup personnalisée avec checkbox
        result = self._show_confirm_dialog(
            "Enregistrement réussi",
            f"Brochage enregistré dans :\n{filepath}",
            "Charger comme référence active",
            default_checked=True
        )

        if result is not None:
            confirm, load_as_reference = result
            if load_as_reference:
                filename = os.path.basename(filepath)
                self.references[filename] = {"path": filepath, "data": data}
                self.active_reference = filename
                self.update_reference_display()
                self.log_line(f"Chargé comme référence active : {filename}")

    def _finish_err(self, msg):
        self.log_line("ERREUR: " + msg)
        self.set_status("Erreur.")
        self.save_btn.configure(state="normal")
        messagebox.showerror("Erreur", msg)

    def _run_test_get_json(self, port, baud, timeout, cmd_bytes):
        """
        Envoie la commande, puis lit jusqu'à obtenir un JSON valide.
        Utilise le port série déjà ouvert (self.serial_port)
        """
        if self.serial_port is None or not self.serial_port.is_open:
            raise RuntimeError("Le port série n'est pas ouvert. Identifiez d'abord le testeur.")

        # Timeout de lecture côté serial : petit, on boucle.
        hard_deadline = time.time() + max(2.0, timeout * 4.0)
        buf = b""

        ser = self.serial_port

        # Flush des buffers pour éliminer les caractères résiduels
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.05)

        # Envoi de la commande
        self.after(0, lambda: self.log_line(f"Envoi commande: {cmd_bytes}"))
        ser.write(cmd_bytes)
        ser.flush()

        # Petit délai après l'envoi pour laisser le testeur traiter la commande
        time.sleep(0.1)

        # Lecture boucle
        while time.time() < hard_deadline:
            chunk = ser.read(4096)
            if chunk:
                buf += chunk
                # Log de débogage pour voir ce qui est reçu
                self.after(0, lambda c=chunk: self.log_line(f"DEBUG: Reçu {len(c)} octets: {c[:100]}"))
                # Essai de décodage
                txt = buf.decode("utf-8", errors="ignore")

                # Heuristique: cherche une sous-chaîne qui ressemble à un JSON objet
                start = txt.find("{")
                end = txt.rfind("}")
                if start != -1 and end != -1 and end > start:
                    candidate = txt[start : end + 1].strip()
                    try:
                        obj = json.loads(candidate)
                        # Vérif format attendu: dict pin -> list
                        if not isinstance(obj, dict):
                            raise ValueError("Le JSON reçu n'est pas un objet/dictionnaire.")
                        return obj
                    except json.JSONDecodeError:
                        # continue à lire, le JSON n'est pas complet
                        pass
            else:
                # rien reçu ce cycle
                pass

        # Si on sort de boucle: pas de JSON valide
        preview = buf.decode("utf-8", errors="ignore")[-300:]
        raise TimeoutError(
            "Timeout: impossible d'obtenir un JSON valide.\n"
            f"Derniers octets reçus (aperçu):\n{preview}"
        )

    def on_closing(self):
        """Fermeture propre de l'application"""
        # Déconnecter le port série si ouvert
        if self.serial_port is not None:
            try:
                self.serial_port.close()
                self.log_line("✓ Port série fermé proprement")
            except:
                pass
        # Fermer l'application
        self.destroy()


if __name__ == "__main__":
    app = CableTesterGUI()
    app.mainloop()

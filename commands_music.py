import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
from collections import deque
import asyncio
from typing import Dict, Optional

class QueueView(discord.ui.View):
    def __init__(self, queue_items, music_queue, per_page=10):
        super().__init__(timeout=180)
        self.queue_items = queue_items
        self.music_queue = music_queue
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max((len(queue_items) - 1) // per_page + 1, 1)
        self.update_button_states()

    def update_button_states(self):
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= self.total_pages - 1
        self.last_page.disabled = self.current_page >= self.total_pages - 1

    def get_current_page_content(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        current_items = self.queue_items[start:end]
        
        content = "**Cola de Reproducción**\n\n"
        for i, item in enumerate(current_items, start=start + 1):
            # Obtener los estados
            state = item.get('state', '⏳')
            shuffle_status = item.get('shuffle_status', '▶')
            
            # Construir la línea con todos los indicadores
            content += f"`{i}.` {state}{shuffle_status} **{item['title']}** (Añadido por: {item['added_by']})\n"
        
        content += f"\nPágina {self.current_page + 1}/{self.total_pages}"
        
        if self.music_queue.is_adding_to_queue:
            content += f"\n\n⏳ Aún hay {self.music_queue.pending_items} elementos siendo agregados a la cola..."
        
        return content

    @discord.ui.button(label="<<", style=discord.ButtonStyle.gray)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self.update_button_states()
        await interaction.response.edit_message(content=self.get_current_page_content(), view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.gray)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        self.update_button_states()
        await interaction.response.edit_message(content=self.get_current_page_content(), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_button_states()
        await interaction.response.edit_message(content=self.get_current_page_content(), view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.gray)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.total_pages - 1
        self.update_button_states()
        await interaction.response.edit_message(content=self.get_current_page_content(), view=self)
class MusicQueue:
    def __init__(self):
        self.queue = deque()
        self.download_queue = deque()
        self.current = None
        self.downloading = False
        self._download_task = None
        self.is_adding_to_queue = False
        self.pending_items = 0
        self.play_order = []
        self.song_ids = {}
        self.next_id = 0
        self.pending_entries = []
        self.shuffle_mode = False
        self.download_limit = 3
        self.processed_count = 0
        self.shuffle_batch = 0
        self.last_shuffle_time = None
        self.processed_count = 0
        self.pending_shuffle = False
        self.shuffle_active = False  # Nueva bandera para indicar si el shuffle está activo
        self.batch_size = 20  # Añadido: Define el tamaño del lote para el shuffle


    def generate_song_id(self):
        song_id = self.next_id
        self.next_id += 1
        return song_id

    def add(self, item):
        """Añade una canción a la cola con el estado apropiado."""
        song_id = self.generate_song_id()
        item['id'] = song_id
        
        # Asignar estado de mezcla basado en si el shuffle está activo
        if self.shuffle_active:
            item['shuffle_status'] = "❇️"
            self.processed_count += 1  # Solo incrementar si shuffle está activo
            
            # Verificar si necesitamos mezclar
            if self.processed_count >= self.batch_size:
                self.pending_shuffle = True  # Marcar para mezcla en el próximo ciclo
        else:
            item['shuffle_status'] = "▶️"
            
        self.song_ids[song_id] = item
        self.queue.append(song_id)
        
        if not self.play_order:
            self.play_order = list(self.download_queue) + list(self.queue)
        else:
            self.play_order.append(song_id)


    def _update_shuffle_order(self):
        """Actualiza el orden de reproducción cuando se agregan nuevas canciones"""
        import random
        if not self.play_order:
            return
        
        # Obtener todos los IDs actuales
        all_ids = list(self.download_queue) + list(self.queue)
        # Agregar nuevos IDs al orden de reproducción
        new_ids = set(all_ids) - set(self.play_order)
        if new_ids:
            new_ids_list = list(new_ids)
            random.shuffle(new_ids_list)
            self.play_order.extend(new_ids_list)

    async def shuffle(self):
        """Marca las canciones pendientes con ❇️ y mezcla las ya procesadas."""
        from datetime import datetime
        import random
        
        # Marcar el momento del shuffle
        self.last_shuffle_time = datetime.now()
        self.pending_shuffle = True
        self.shuffle_active = True  # Activar el modo shuffle
        
        # Obtener todas las canciones actuales
        current_songs = list(self.download_queue) + list(self.queue)
        if not current_songs:
            return "EMPTY"

        # Marcar canciones pendientes con ❇️
        for song_id in self.queue:
            self.song_ids[song_id]['shuffle_status'] = "❇️"
        
        # Mezclar solo las canciones ya descargadas
        downloaded_songs = list(self.download_queue)
        if downloaded_songs:
            random.shuffle(downloaded_songs)
            for song_id in downloaded_songs:
                self.song_ids[song_id]['shuffle_status'] = "🔀"
        
        # Actualizar las colas
        self.download_queue = deque(downloaded_songs)
        
        # Actualizar el orden de reproducción
        self.play_order = list(self.download_queue) + list(self.queue)
        
        return "SUCCESS"



    def pop(self):
        """Obtiene la siguiente canción a reproducir."""
        if not self.play_order and (self.download_queue or self.queue):
            self.play_order = list(self.download_queue) + list(self.queue)

        while self.play_order:
            next_id = self.play_order[0]
            self.play_order.pop(0)
            
            # Buscar y remover el ID de cualquiera de las colas
            if next_id in self.download_queue:
                self.download_queue.remove(next_id)
                return self.song_ids[next_id]
            elif next_id in self.queue:
                self.queue.remove(next_id)
                return self.song_ids[next_id]
        
        return None

    def show(self):
        """Muestra todas las canciones en la cola respetando el orden de play_order."""
        all_songs = []
        
        # Añadir la canción actual si existe
        if self.current:
            current_copy = dict(self.current)
            current_copy['state'] = "🔊"
            all_songs.append(current_copy)

        # Si no hay play_order, crear uno nuevo
        if not self.play_order and (self.download_queue or self.queue):
            self.play_order = list(self.download_queue) + list(self.queue)

        # Añadir canciones en el orden de play_order
        for song_id in self.play_order:
            if song_id in self.song_ids:
                song = dict(self.song_ids[song_id])
                # Establecer el estado basado en la ubicación real de la canción
                if song_id in self.download_queue:
                    song['state'] = "✅"
                else:
                    song['state'] = "⏳"
                all_songs.append(song)

        return all_songs

    def clear(self):
        """Limpia todas las colas y reinicia el estado"""
        self.queue.clear()
        self.download_queue.clear()
        self.current = None
        self.play_order.clear()
        self.song_ids.clear()
        self.next_id = 0
        self.shuffle_active = False  # Resetear el estado de shuffle
        self.pending_shuffle = False
        self.processed_count = 0
        self.pending_entries.clear()
    
    async def auto_shuffle(self):
        """Mezcla automáticamente la cola."""
        import random

        # Guardar la canción actual
        current_id = None
        if self.current and 'id' in self.current:
            current_id = self.current['id']

        # Combinar canciones procesadas y pendientes
        all_songs = list(self.queue) + list(self.download_queue) + self.pending_entries
        random.shuffle(all_songs)

        # Actualizar colas
        self.queue.clear()
        self.download_queue.clear()
        self.queue.extend(all_songs)

        # Actualizar el orden de reproducción
        self.play_order = list(self.queue)

        # Restaurar la canción actual
        if current_id:
            self.play_order.insert(0, current_id)

        # Reiniciar las canciones descargadas (excepto la actual)
        self.download_queue.clear()
        if current_id:
            self.download_queue.append(current_id)

    async def shuffle_pending(self):
        """Mezcla los elementos marcados con ❇️"""
        import random
        
        # Recolectar todos los IDs de canciones con estado ❇️
        pending_songs = [
            song_id for song_id in self.queue
            if self.song_ids[song_id].get('shuffle_status') == "❇️"
        ]
        
        if not pending_songs:
            return
            
        # Mezclar las canciones pendientes
        random.shuffle(pending_songs)
        
        # Actualizar estados y posiciones
        for song_id in pending_songs:
            self.song_ids[song_id]['shuffle_status'] = "🔀"
        
        # Actualizar la cola manteniendo el orden de las canciones no mezcladas
        non_pending = [
            song_id for song_id in self.queue
            if self.song_ids[song_id].get('shuffle_status') != "❇️"
        ]
        
        # Reconstruir la cola con el nuevo orden
        self.queue = deque(pending_songs + non_pending)
        
        # Actualizar el orden de reproducción
        self.play_order = list(self.download_queue) + list(self.queue)

    async def process_downloads(self):
        while True:
            try:
                downloaded_count = len(self.download_queue) + (1 if self.current else 0)
                
                if downloaded_count < self.download_limit and self.queue and not self.downloading:
                    self.downloading = True
                    try:
                        if self.pending_shuffle and self.processed_count >= self.batch_size:
                            await self.shuffle_pending()
                            self.processed_count = 0
                            self.pending_shuffle = False
                            
                        next_id = self.queue[0]
                        next_song = self.song_ids[next_id]

                        if not next_song.get('downloaded', False):
                            # Aquí va el código de descarga existente
                            pass
                            
                    finally:
                        self.downloading = False

                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error en process_downloads: {str(e)}")
                await asyncio.sleep(1)

async def play_audio(vc, music_queue):
    if music_queue.current:
        try:
            url = music_queue.current['url']
            
            def after_playing(error):
                if error:
                    print(f"Error en la reproducción: {error}")
                asyncio.run_coroutine_threadsafe(play_next(vc, music_queue), vc.loop)

            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn -bufsize 64k'
            }
            
            source = discord.FFmpegPCMAudio(
                url, 
                executable="C:/ffmpeg/bin/ffmpeg.exe",
                **ffmpeg_options
            )
            vc.play(source, after=after_playing)
            
        except Exception as e:
            print(f"Error reproducing audio: {str(e)}")
            await play_next(vc, music_queue)

async def play_next(vc, music_queue):
    await asyncio.sleep(1)
    
    if not vc.is_connected():
        return
        
    next_song = music_queue.pop()
    
    if next_song:
        music_queue.current = next_song
        await play_audio(vc, music_queue)
    elif music_queue.queue or music_queue.is_adding_to_queue:
        # Esperar brevemente por nuevas canciones
        for _ in range(10):  # 5 segundos máximo de espera
            if music_queue.download_queue:
                next_song = music_queue.pop()
                if next_song:
                    music_queue.current = next_song
                    await play_audio(vc, music_queue)
                break
            await asyncio.sleep(0.5)
    else:
        music_queue.current = None
        await vc.disconnect()

def setup_music_commands(bot):
    music_queue = MusicQueue()

    @bot.tree.command(name="play", description="Reproduce una canción o añade a la cola.")
    async def play(interaction: discord.Interaction, query: str = None):
        if not query:
            if not interaction.guild.voice_client or not interaction.guild.voice_client.is_paused():
                await interaction.response.send_message("No hay nada para reanudar.")
                return
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("Reproducción reanudada.")
            return

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("¡Debes estar en un canal de voz!")
            return
        
        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()

        if not music_queue._download_task or music_queue._download_task.done():
            music_queue._download_task = asyncio.create_task(music_queue.process_downloads())

        # Enviar mensaje inicial
        await interaction.response.send_message("Procesando solicitud...")
        original_message = await interaction.original_response()

        try:
            ytdl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'noplaylist': False,
                'extract_flat': 'in_playlist',
                'ignoreerrors': True
            }

            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                try:
                    music_queue.is_adding_to_queue = True
                    
                    if "http" in query:
                        playlist_info = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: ydl.extract_info(query, download=False)
                        )
                    else:
                        search_result = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: ydl.extract_info(f"ytsearch:{query}", download=False)
                        )
                        playlist_info = search_result['entries'][0] if 'entries' in search_result else search_result

                    if 'entries' in playlist_info:
                        entries = [entry for entry in playlist_info['entries'] if entry]
                        music_queue.pending_items = len(entries)
                        await original_message.edit(content=f"Procesando playlist con {music_queue.pending_items} elementos...")
                        
                        # Procesar primera canción inmediatamente
                        if entries:
                            first_entry = entries[0]
                            video_opts = dict(ytdl_opts)
                            video_opts['noplaylist'] = True
                            
                            with yt_dlp.YoutubeDL(video_opts) as video_ydl:
                                try:
                                    video_url = f"https://www.youtube.com/watch?v={first_entry['id']}"
                                    video_info = await asyncio.get_event_loop().run_in_executor(
                                        None,
                                        lambda: video_ydl.extract_info(video_url, download=False)
                                    )
                                    
                                    if video_info:
                                        music_queue.add({
                                            'title': video_info.get('title', 'Unknown Title'),
                                            'url': video_info.get('url', video_url),
                                            'added_by': interaction.user.name,
                                            'downloaded': True  # Marcar como descargada
                                        })
                                        
                                        # Iniciar reproducción inmediatamente
                                        if not vc.is_playing() and not music_queue.current:
                                            next_song = music_queue.pop()
                                            if next_song:
                                                music_queue.current = next_song
                                                await play_audio(vc, music_queue)
                                    
                                    music_queue.pending_items -= 1
                                    
                                    # Procesar resto de la playlist en segundo plano
                                    for entry in entries[1:]:
                                        try:
                                            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                                            video_info = await asyncio.get_event_loop().run_in_executor(
                                                None,
                                                lambda: video_ydl.extract_info(video_url, download=False)
                                            )
                                            
                                            if video_info:
                                                music_queue.add({
                                                    'title': video_info.get('title', 'Unknown Title'),
                                                    'url': video_info.get('url', video_url),
                                                    'added_by': interaction.user.name,
                                                    'downloaded': True
                                                })
                                                
                                            music_queue.pending_items -= 1
                                            
                                            # Actualizar mensaje cada 5 canciones procesadas
                                            if music_queue.pending_items % 5 == 0:
                                                await original_message.edit(
                                                    content=f"Procesando playlist... {music_queue.pending_items} elementos restantes"
                                                )
                                                
                                        except Exception as e:
                                            print(f"Error procesando video de playlist: {str(e)}")
                                            music_queue.pending_items -= 1
                                            continue
                                            
                                except Exception as e:
                                    print(f"Error procesando primera canción: {str(e)}")
                                    music_queue.pending_items -= 1
                        
                        music_queue.is_adding_to_queue = False
                        await original_message.edit(content="Playlist procesada completamente.")
                        
                    else:  # Es un solo video
                        # Añadir a la cola
                        music_queue.add({
                            'title': playlist_info['title'],
                            'url': playlist_info.get('url', playlist_info.get('webpage_url')),
                            'added_by': interaction.user.name,
                            'downloaded': False
                        })
                        
                        await original_message.edit(
                            content=f"**{playlist_info['title']}** añadido a la cola por {interaction.user.name}."
                        )
                        
                        # Iniciar reproducción si no hay nada reproduciéndose
                        if not vc.is_playing() and not music_queue.current:
                            for _ in range(10):  # Esperar hasta 5 segundos
                                if music_queue.download_queue:
                                    next_song = music_queue.pop()
                                    if next_song:
                                        music_queue.current = next_song
                                        await play_audio(vc, music_queue)
                                        break
                                await asyncio.sleep(0.5)

                    music_queue.is_adding_to_queue = False

                except Exception as e:
                    music_queue.is_adding_to_queue = False
                    await original_message.edit(content=f"Error al procesar la URL: {str(e)}")
                    return

        except Exception as e:
            music_queue.is_adding_to_queue = False
            await original_message.edit(content=f"Error general: {str(e)}")

    @bot.tree.command(name="queue", description="Muestra la cola actual.")
    async def queue(interaction: discord.Interaction):
        all_songs = music_queue.show()

        if not all_songs:
            await interaction.response.send_message("La cola está vacía.")
            return

        per_page = 10  # Número de elementos por página
        total_pages = (len(all_songs) - 1) // per_page + 1
        current_page = 0  # Inicialmente mostrar la primera página

        def get_page_content(page, per_page, queue_items, total_pages, music_queue):
            start = page * per_page
            end = start + per_page
            content = "**Cola de Reproducción**\n\n"

            for i, item in enumerate(queue_items[start:end], start=start + 1):
                state = item.get('state', "⏳")
                shuffle_status = item.get('shuffle_status', "▶")  # `▶`, `🔀`, o `❇️`
                content += f"`{i}.` {state}{shuffle_status} **{item['title']}** (Añadido por: {item['added_by']})\n"

            content += f"\nPágina {page + 1}/{total_pages}"
            if music_queue.is_adding_to_queue:
                content += f"\n⏳ Aún hay {music_queue.pending_items} elementos siendo agregados a la cola..."
            return content

        # Enviar la primera página
        content = get_page_content(
            page=current_page,
            per_page=per_page,
            queue_items=all_songs,
            total_pages=total_pages,
            music_queue=music_queue
        )
        view = QueueView(all_songs, music_queue, per_page)
        await interaction.response.send_message(content=content, view=view)

    @bot.tree.command(name="shuffle", description="Mezcla las canciones en la cola.")
    async def shuffle(interaction: discord.Interaction):
        result = await music_queue.shuffle()
        
        if result == "EMPTY":
            await interaction.response.send_message("No hay canciones en la cola para mezclar.")
            return

        # Cancelar las descargas actuales y priorizar las nuevas
        if music_queue._download_task and not music_queue._download_task.done():
            music_queue._download_task.cancel()
        music_queue._download_task = asyncio.create_task(music_queue.process_downloads())

        # Verificar si hay reproducción activa
        vc = interaction.guild.voice_client
        if vc and not vc.is_playing() and music_queue.play_order:
            music_queue.current = music_queue.pop()
            await play_audio(vc, music_queue)

        await interaction.response.send_message("🔀 Cola mezclada exitosamente.")


    @bot.tree.command(name="pause", description="Pausa la reproducción.")
    async def pause(interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("No hay nada reproduciendo.")
            return
        vc.pause()
        await interaction.response.send_message("Reproducción pausada.")

    @bot.tree.command(name="stop", description="Detiene la reproducción y limpia la cola.")
    async def stop(interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
        music_queue.clear()
        await interaction.response.send_message("Reproducción detenida y cola eliminada.")

    @bot.tree.command(name="skip", description="Salta la canción actual.")
    async def skip(interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("No hay nada reproduciendo para saltar.")
            return
        vc.stop()
        await interaction.response.send_message("Canción saltada.")

    @bot.tree.command(name="remove", description="Elimina una canción de la cola.")
    async def remove(interaction: discord.Interaction, index: int):
        try:
            # Ajustar para tener en cuenta ambas colas
            all_queue = list(music_queue.download_queue) + list(music_queue.queue)
            if 1 <= index <= len(all_queue):
                if index <= len(music_queue.download_queue):
                    removed = music_queue.download_queue[index - 1]
                    del music_queue.download_queue[index - 1]
                else:
                    adjusted_index = index - len(music_queue.download_queue) - 1
                    removed = music_queue.queue[adjusted_index]
                    del music_queue.queue[adjusted_index]
                await interaction.response.send_message(f"**{removed['title']}** eliminado de la cola.")
            else:
                await interaction.response.send_message("Índice fuera de rango.")
        except Exception as e:
            await interaction.response.send_message(f"Error al eliminar: {e}")
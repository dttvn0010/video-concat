import os
import subprocess
import re
from dataclasses import dataclass
from flask import Flask, request, render_template, redirect

TMP1 = 'tmp/tmp1.mp4'
TMP2 = 'tmp/tmp2.mp4'

@dataclass
class VideoInfo:
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool

def execute_cmd(cmd):
    return subprocess.getoutput(cmd)
    
def get_video_info(fn):
    txt = execute_cmd(f'ffmpeg -i {fn}')
    match = re.search('Duration: ([0-9]{2}):([0-9]{2}):([0-9]{2}).([0-9]{2})', txt)
    duration = float(match.group(1)) * 3600 + float(match.group(2)) * 60 + float(match.group(3)) + float(match.group(4))/100
    match = re.search('(([0-9]+)(\\.([0-9]+)){0,1}) fps', txt)
    fps = float(match.group(1))
    match = re.search('Video:(.)*([, ][0-9]+)x([0-9]+[, ])', txt)
    width = int(match.group(2).replace(',',''))
    height = int(match.group(3).replace(',',''))
    has_audio = 'Audio:' in txt
    return VideoInfo(duration, fps, width, height, has_audio)

def remove_file(fn):
    if os.path.exists(fn):
        os.remove(fn)

def concat_video(fn1, fn2, out_fn):
    vid_info1 = get_video_info(fn1)
    vid_info2 = get_video_info(fn2)
    print(vid_info1.fps, vid_info1.width, vid_info1.height)
    print(vid_info2.fps, vid_info2.width, vid_info2.height)
    width = max(vid_info1.width, vid_info2.width)
    height = max(vid_info1.height, vid_info2.height)
    fps = max(vid_info1.fps, vid_info2.fps)
    print(fps, width, height)

    if vid_info1.width != width or height != vid_info2.height or vid_info1.fps != fps:
        if vid_info1.width != width or vid_info1.height != height or vid_info1.fps != fps:
            print('Converting video 1 before concatenation ...')
            remove_file(TMP1)
            execute_cmd(f'ffmpeg -i {fn1} -filter:v "scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}" -c:v libx264 -crf 23 -preset fast {TMP1}')
            fn1 = TMP1
        
        if vid_info2.width != width or vid_info2.height != height or vid_info2.fps != fps:
            print('Converting video 2 before concatenation ...')
            remove_file(TMP2)
            execute_cmd(f'ffmpeg -i {fn2} -filter:v "scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}" -c:v libx264 -crf 23 -preset fast {TMP2}')
            fn2 = TMP2

    remove_file(out_fn)
    
    print('Concatenating 2 videos ...')

    if vid_info1.has_audio and vid_info2.has_audio:
        execute_cmd(f'ffmpeg -i {fn1} -i {fn2} -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]" -map "[outv]" -map "[outa]" {out_fn}')

    elif vid_info1.has_audio and not vid_info2.has_audio:
        execute_cmd(f'ffmpeg -i {fn1} -i {fn2} -f lavfi -i anullsrc=r=44100:cl=stereo -shortest -filter_complex "[0:v][0:a][1:v][2:a]concat=n=2:v=1:a=1[outv][outa]" -map "[outv]" -map "[outa]" {out_fn}')

    elif not vid_info1.has_audio and vid_info2.has_audio:
        execute_cmd(f'ffmpeg -i {fn1} -i {fn2} -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[outv];anullsrc=channel_layout=stereo:r=44100:d={vid_info1.duration}[outa];[outa][1:a]concat=n=2:v=0:a=1[outa_final]" -map "[outv]" -map "[outa_final]" {out_fn}')

    else:
        execute_cmd(f'ffmpeg -i {fn1} -i {fn2} -filter_complex "[0:v][1:v]concat=n=2:v=1[outv]" -map "[outv]" {out_fn}')
        
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')
    
@app.route('/upload', methods=['POST'])
def concate():
    vid1 = request.files.get('vid1')
    vid2 = request.files.get('vid2')
    if (vid1 == None or vid1.filename == '' or vid2 == None or vid2.filename == ''):
        return "Please upload both videos"
    
    vid1_name, vid1_ext = os.path.splitext(vid1.filename)
    vid2_name, vid2_ext = os.path.splitext(vid2.filename)
    
    fn1 = 'tmp/1' + vid1_ext
    fn2 = 'tmp/2' + vid2_ext
    out_fn = 'static/output.mp4'
    
    vid1.save(fn1)
    vid2.save(fn2)
    
    concat_video(fn1, fn2, out_fn)
    
    return redirect('/' + out_fn)
    

if __name__ == '__main__':
    app.run()
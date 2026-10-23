$ff=(Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName
$pr=(Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffprobe.exe | Select-Object -First 1).FullName
Set-Location "D:\клод\montag"; (Get-Process -Id $PID).PriorityClass='BelowNormal'
function CountFrames($f){ if(Test-Path $f){ [int](& $pr -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 $f 2>$null) } else { 0 } }
$herVf="curves=all='0/0.03 0.12/0.20 0.3/0.36 0.5/0.52 0.8/0.8 1/1',colorbalance=rm=-0.08:rh=-0.04"
"h5_new frames=$(CountFrames 'work\prism\herP\h5_new.mp4')"
Copy-Item work\prism\herP\h5_new.mp4 work\prism\herP\h5.mp4 -Force
# rebuild final chunk 5 (frames 45000-54000)
$a=45000;$b=54000;$out="work\prism\finalC\f5.mp4"
for($try=1;$try -le 6;$try++){
  if((CountFrames $out) -eq 9000){ break }
  if(Test-Path $out){ [IO.File]::Delete((Resolve-Path $out).Path) }
  & $ff -y -v error -f concat -safe 0 -i work\prism\clipsG\list.txt -i work\prism\herP\h5.mp4 `
    -filter_complex "[0:v]setpts=N/(30*TB),trim=start_frame=${a}:end_frame=${b},setpts=PTS-STARTPTS,fps=30[f];[1:v]$herVf[h];[f][h]hstack=shortest=1[o]" `
    -map "[o]" -frames:v 9000 -an -threads 2 -filter_threads 1 -filter_complex_threads 1 -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p $out 2>$null
  "f5 try $try frames=$(CountFrames $out)"
}
& $ff -y -v error -f concat -safe 0 -i work\prism\finalC\list_cut.txt -c copy work\prism\video_cut2.mp4 2>$null
"concat frames=$(CountFrames 'work\prism\video_cut2.mp4') (expect 63363)"
& $ff -y -v error -i work\prism\video_cut2.mp4 -i out\prism_full_7030_color_music_v2.mp4 -map 0:v -map 1:a -c copy -t 2112.1 -movflags +faststart out\prism_full_7030_color_music_v3.mp4 2>$null
"mux exit=$LASTEXITCODE"

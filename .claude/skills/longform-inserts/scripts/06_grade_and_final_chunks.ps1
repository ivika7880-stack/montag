$ff = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName
$pr = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffprobe.exe | Select-Object -First 1).FullName
Set-Location "D:\клод\montag"
$ci = [cultureinfo]::InvariantCulture
New-Item -ItemType Directory -Force work\prism\clipsG | Out-Null
New-Item -ItemType Directory -Force work\prism\finalC | Out-Null
$rows = Get-Content work\prism\col_all.json -Raw | ConvertFrom-Json
function FrameCount($f) { if (Test-Path $f) { [int](& $pr -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 $f 2>$null) } else { 0 } }
# 1. graded clips (insert panel)
$list = @()
foreach ($r in $rows) {
    $src = "work\prism\clipsF\c{0:000}.mp4" -f $r.i; $out = "work\prism\clipsG\g{0:000}.mp4" -f $r.i
    if (-not (Test-Path $src)) { continue }
    $need = FrameCount $src
    for ($try = 1; $try -le 5; $try++) {
        if ((FrameCount $out) -eq $need) { break }
        if (Test-Path $out) { [IO.File]::Delete((Resolve-Path $out).Path) }
        $vf = "eq=gamma={0}:saturation={1}" -f ([double]$r.gamma).ToString($ci), ([double]$r.satf).ToString($ci)
        & $ff -y -v error -i $src -vf $vf -threads 2 -c:v libx264 -crf 14 -preset fast -pix_fmt yuv420p $out 2>$null
    }
    $list += "file 'g{0:000}.mp4'" -f $r.i
}
$list | Set-Content work\prism\clipsG\list.txt -Encoding ascii
"graded clips: $($list.Count)"
# 2. final chunks: graded film + graded speaker panel, retimed to exact 30 fps
$TOTAL = 63369
$herVf = "curves=all='0/0.03 0.12/0.20 0.3/0.36 0.5/0.52 0.8/0.8 1/1',colorbalance=rm=-0.08:rh=-0.04"
$flist = @()
for ($k = 0; $k -lt 7; $k++) {
    $a = $k * 9000; $b = if ($k -eq 6) { $TOTAL } else { $a + 9000 }; $fr = $b - $a
    $out = "work\prism\finalC\f$k.mp4"
    for ($try = 1; $try -le 6; $try++) {
        if ((FrameCount $out) -eq $fr) { break }
        if (Test-Path $out) { [IO.File]::Delete((Resolve-Path $out).Path) }
        & $ff -y -v error -f concat -safe 0 -i work\prism\clipsG\list.txt -i "work\prism\herP\h$k.mp4" `
            -filter_complex "[0:v]setpts=N/(30*TB),trim=start_frame=${a}:end_frame=${b},setpts=PTS-STARTPTS,fps=30[f];[1:v]$herVf[h];[f][h]hstack=shortest=1[o]" `
            -map "[o]" -frames:v $fr -an -threads 2 -filter_threads 1 -filter_complex_threads 1 -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p $out 2>$null
        "chunk $k try $try exit=$LASTEXITCODE"
    }
    $flist += "file 'f$k.mp4'"
}
$flist | Set-Content work\prism\finalC\list.txt -Encoding ascii
& $ff -y -v error -f concat -safe 0 -i work\prism\finalC\list.txt -c copy work\prism\video_color.mp4 2>$null
"video concat exit=$LASTEXITCODE"
& $ff -y -v error -i work\prism\video_color.mp4 -i "D:\клод\исходники\3\т.MOV" -map 0:v -map 1:a:0 -c:v copy -c:a aac -b:a 192k -t 2112.30 -movflags +faststart out\prism_full_7030_color.mp4 2>$null
"mux exit=$LASTEXITCODE"

$ErrorActionPreference = "Continue"
Set-Location "D:\клод\montag"
$ff = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName
$dir = "C:\Users\user\Downloads\Prism Rond [WEB-DL 1080p]"
$ci = [cultureinfo]::InvariantCulture
$END = 2112.30                     # video/audio length of the source (s)
$sel = Get-Content work\prism\selection_full.json -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force work\prism\clipsF | Out-Null
$list = @(); $i = 0
foreach ($s in $sel) {
    $t0 = [double]$s.t0; $t1 = [math]::Min([double]$s.t1, $END)
    if ($t1 -le $t0 + 0.05) { $i++; continue }
    $fr = [int]([math]::Round($t1 * 30) - [math]::Round($t0 * 30))
    $out = "work\prism\clipsF\c{0:000}.mp4" -f $i
    if (-not (Test-Path $out) -or (Get-Item $out).Length -lt 20000) {
        $epn = '{0:00}' -f [int]$s.ep
        & $ff -y -v error -ss ([double]$s.start).ToString($ci) -t ((($fr / 30.0) + 1).ToString($ci)) -i "$dir\Prism Rondo $epn.mkv" -an `
            -vf "fps=30,scale=-2:1080,crop=1344:1080,setsar=1" -frames:v $fr -c:v libx264 -crf 16 -preset fast -pix_fmt yuv420p $out 2>$null
    }
    $list += "file 'c{0:000}.mp4'" -f $i
    $i++
}
$list | Set-Content work\prism\clipsF\list.txt -Encoding ascii
"clips done: $($list.Count)"
& $ff -y -v error -f concat -safe 0 -i work\prism\clipsF\list.txt -c copy work\prism\filmF.mp4 2>$null
"film done"
if (-not (Test-Path work\prism\herF.mp4)) {
    & $ff -y -v error -i "D:\клод\исходники\3\т.MOV" -t $END -vf "fps=30,scale=-2:1080,crop=576:1080:15:0,setsar=1" -an -c:v libx264 -crf 14 -preset fast -pix_fmt yuv420p work\prism\herF.mp4 2>$null
}
"her done"
& $ff -y -v error -i work\prism\filmF.mp4 -i work\prism\herF.mp4 -t $END -i "D:\клод\исходники\3\т.MOV" `
    -filter_complex "[0:v][1:v]hstack=shortest=1[out]" -map "[out]" -map 2:a -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p `
    -c:a aac -b:a 192k -movflags +faststart -t $END out\prism_full_7030.mp4 2>$null
"FINAL exit=$LASTEXITCODE"

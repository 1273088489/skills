param(
  [Parameter(Mandatory=$true)][string]$OutFile
)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$img = [System.Windows.Forms.Clipboard]::GetImage()
if ($null -eq $img) {
  Write-Error "剪贴板中没有图片"
  exit 1
}
$img.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$img.Dispose()
Write-Output "已保存剪贴板图片到 $OutFile"

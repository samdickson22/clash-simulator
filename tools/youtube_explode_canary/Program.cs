using System.Text.Json;
using System.Net;
using System.Net.Http.Headers;
using YoutubeExplode;
using YoutubeExplode.Exceptions;
using YoutubeExplode.Videos.Streams;

const long maximumBytes = 500L * 1024L * 1024L;

if (args.Length != 2)
    throw new ArgumentException("usage: YoutubeExplodeCanary <public-watch-url> <output-path>");

var publicUrl = args[0];
var outputPath = Path.GetFullPath(args[1]);
if (!Uri.TryCreate(publicUrl, UriKind.Absolute, out var uri)
    || uri.Scheme != Uri.UriSchemeHttps
    || uri.Host is not ("www.youtube.com" or "youtube.com"))
{
    throw new ArgumentException("only an HTTPS public YouTube watch URL is accepted");
}

Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
if (File.Exists(outputPath))
    throw new IOException("output already exists");

using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(5));
using var http = new HttpClient();
http.DefaultRequestHeaders.UserAgent.Add(
    new ProductInfoHeaderValue("YoutubeDownloader", "6.6.1-canary")
);
using var youtube = new YoutubeClient(http, Array.Empty<Cookie>());
StreamManifest? manifest = null;
for (var attempt = 0; attempt < 3; attempt++)
{
    try
    {
        manifest = await youtube.Videos.Streams.GetManifestAsync(publicUrl, timeout.Token);
        break;
    }
    catch (VideoUnavailableException) when (attempt < 2)
    {
        await Task.Delay(TimeSpan.FromSeconds(10 * (attempt + 1)), timeout.Token);
    }
}
if (manifest is null)
    throw new InvalidOperationException("bounded manifest retries produced no result");
var candidates = manifest
    .GetVideoOnlyStreams()
    .Where(stream => stream.Size.Bytes is > 0 and <= maximumBytes)
    .OrderByDescending(stream => stream.VideoQuality.MaxHeight)
    .ThenByDescending(stream => stream.Bitrate.BitsPerSecond)
    .ToArray();

var selected = candidates.FirstOrDefault()
    ?? throw new InvalidOperationException("no bounded video-only stream was available");

var partialPath = outputPath + ".partial";
try
{
    await youtube.Videos.Streams.DownloadAsync(selected, partialPath, cancellationToken: timeout.Token);
    var actualBytes = new FileInfo(partialPath).Length;
    if (actualBytes != selected.Size.Bytes || actualBytes > maximumBytes)
        throw new IOException("downloaded stream size violated the declared bound");
    File.Move(partialPath, outputPath);
    Console.WriteLine(JsonSerializer.Serialize(new
    {
        schema = "clasher.youtube_explode_public_stream.v1",
        sourceUrl = publicUrl,
        stream = new
        {
            container = selected.Container.Name,
            width = selected.VideoResolution.Width,
            height = selected.VideoResolution.Height,
            framesPerSecond = selected.VideoQuality.Framerate,
            bitrateBitsPerSecond = selected.Bitrate.BitsPerSecond,
            declaredBytes = selected.Size.Bytes,
            actualBytes,
            videoCodec = selected.VideoCodec,
        },
    }));
}
catch
{
    if (File.Exists(partialPath))
        File.Delete(partialPath);
    throw;
}

import subprocess
from dotenv import dotenv_values
from pprint import pprint
from VideoIndexerClient.Consts import Consts
from VideoIndexerClient.VideoIndexerClient import VideoIndexerClient
import asyncio
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="VideoIndexerFunction")
@app.route(route="index-video", methods=["POST"])
async def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # .env ファイルから設定を読み込む
        config = dotenv_values(".env")

        AccountName = config.get('AccountName')
        ResourceGroup = config.get('ResourceGroup')
        SubscriptionId = config.get('SubscriptionId')

        ApiVersion = '2024-01-01'
        ApiEndpoint = 'https://api.videoindexer.ai'
        AzureResourceManager = 'https://management.azure.com'

        # constsを作成
        consts = Consts(ApiVersion, ApiEndpoint, AzureResourceManager, AccountName, ResourceGroup, SubscriptionId)

        # 認証
        client = VideoIndexerClient()

        # 非同期認証処理
        await client.authenticate_async(consts)

        # アカウント情報を取得
        await client.get_account_async()

        # リクエストからパラメータを取得
        video_url = req.params.get("video_url")
        video_name = req.params.get("video_name", "default_video")
        video_description = req.params.get("video_description", "default_video")

        if not video_url:
            return func.HttpResponse(
                body="Missing 'video_url' parameter",
                status_code=400
            )

        privacy = 'private'
        ExcludedAI = []
        new_filepath = f"{video_name}_processed.mp4"

        # ffmpeg コマンド
        cmd = [
            '/usr/bin/ffmpeg',
            '-i', video_url,
            '-vf', "scale=1280:-2,fps=30",
            '-vcodec', 'libx265',
            new_filepath
        ]

        # subprocessの非同期実行
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        # 標準出力とエラーを待機
        stdout, stderr = await process.communicate()

        # 出力とエラーの確認
        if process.returncode == 0:
            print("ffmpegの実行成功")
        else:
            print(f"エラーが発生しました: {stderr.decode()}")
            return func.HttpResponse(
                body=f"ffmpeg processing failed: {stderr.decode()}",
                status_code=500
            )

        # Video Indexerにビデオをアップロードしてインデックスを作成
        video_id = await client.upload_url_async(video_name, new_filepath, ExcludedAI, False)
        await client.wait_for_index_async(video_id)

        # インサイトを取得
        insights = await client.get_video_async(video_id)

        # インサイトを表示
        pprint(insights)

        return func.HttpResponse(
            body="Video indexed successfully",
            status_code=200
        )

    except Exception as e:
        return func.HttpResponse(
            body=f"Error: {str(e)}",
            status_code=500
        )

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as dotenv from 'dotenv';
import * as path from 'path';
import { AssetCode, LayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';

export class GmailapiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    dotenv.config();

    // 外部ライブラリのインストール
    const lambdaLayer = new LayerVersion(this, "GmailSummaryLayer", {
      code: AssetCode.fromAsset(path.join(__dirname, '../layer')),
      compatibleRuntimes: [Runtime.PYTHON_3_9],
    });

    // Lambda関数の作成
    const lambdaFunction = new lambda.Function(this, 'GmailSummaryLambda', {
      functionName: 'gmail_summary',
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda')),// Lambda関数のコードディレクトリ
      handler: 'main.handler',
      environment: {
        OPENAI_API_KEY: process.env.OPENAI_API_KEY || 'empty',
        LINE_ACCESS_TOKEN: process.env.LINE_ACCESS_TOKEN || 'empty',
      },
      memorySize: 256,
      timeout: cdk.Duration.seconds(120),
      layers: [lambdaLayer],
    });

    // EventBridgeルールの作成
    const rule = new events.Rule(this, 'DailyRule', {
      schedule: events.Schedule.cron({ hour: '23', minute: '0' }), // 毎日午前8時(日本時間)に実行
    });
    rule.addTarget(new targets.LambdaFunction(lambdaFunction));
  }
}